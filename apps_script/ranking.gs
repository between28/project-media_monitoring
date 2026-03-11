function rankArticles() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
  var rawRecords = readSheetRecords_(MM.SHEET_NAMES.RAW);
  var lookbackStart = getLookbackStart_(config, new Date());
  var representativeRecords = rawRecords.filter(isRepresentativeRecord_);
  var lookbackRecords = representativeRecords.filter(function(record) {
    return isWithinLookback_(record, lookbackStart);
  });
  var themeStats = buildThemeStats_(lookbackRecords, config);

  rawRecords.forEach(function(record) {
    if (!isRepresentativeRecord_(record)) {
      record.importance_score = 0;
      return;
    }

    var themeKey = deriveThemeKey_(record, config);
    var score = Number(record.policy_score || 0);
    var themeStat = themeStats[themeKey] || { count: 1, sourceCount: 1 };

    score += getSourcePriority_(record.source_name, config);
    score += getFreshnessBoost_(record);

    if (record.frame_category === '비판 / 우려') {
      score += Number(config.ranking.criticalFrameBoost || 2);
    }

    if (hasNegativeSignal_(record, config)) {
      score += 1;
    }

    if (isOpinionItem_(record, config)) {
      score += Number(config.ranking.opinionBoost || 3);
    }

    score += Math.min(Math.max(themeStat.count - 1, 0), 3) * Number(config.ranking.repeatedNarrativeBonus || 1);
    score += Math.min(Math.max(themeStat.sourceCount - 1, 0), 2);

    record.importance_score = Math.round(score * 10) / 10;
    record.notes = upsertTaggedNote_(record.notes, 'theme', themeKey);
  });

  overwriteSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, rawRecords);

  var processedRecords = rawRecords.filter(function(record) {
    return isRepresentativeRecord_(record) &&
      Number(record.policy_score || 0) >= Number(config.scoring.highRelevanceThreshold || 6) &&
      isWithinLookback_(record, lookbackStart);
  });

  processedRecords.sort(compareProcessedRecords_);

  var rankedRows = processedRecords.slice(0, Number(config.collection.maxProcessedRows || 50)).map(function(record, index) {
    var output = cloneObject_(record);
    output.rank = index + 1;
    return output;
  });

  overwriteSheetRecords_(MM.SHEET_NAMES.PROCESSED, MM.PROCESSED_COLUMNS, rankedRows);
  return rankedRows;
}

function buildThemeStats_(records, config) {
  var stats = {};

  records.forEach(function(record) {
    var themeKey = deriveThemeKey_(record, config);

    if (!stats[themeKey]) {
      stats[themeKey] = {
        count: 0,
        sources: {}
      };
    }

    stats[themeKey].count += 1;
    stats[themeKey].sources[record.source_name] = true;
  });

  Object.keys(stats).forEach(function(themeKey) {
    stats[themeKey].sourceCount = Object.keys(stats[themeKey].sources).length;
  });

  return stats;
}

function deriveThemeKey_(record, config) {
  var keywords = splitKeywords_(record.keyword);
  var genericLookup = {};

  (config.genericThemeKeywords || []).forEach(function(keyword) {
    genericLookup[keyword] = true;
  });

  var specificKeywords = keywords.filter(function(keyword) {
    return !genericLookup[keyword];
  });
  var themeKeywords = specificKeywords.length ? specificKeywords : keywords;

  if (!themeKeywords.length) {
    var title = String(record.title || '');
    if (title.indexOf('용산') !== -1) {
      themeKeywords.push('용산');
    }
    if (title.indexOf('태릉') !== -1) {
      themeKeywords.push('태릉');
    }
    if (title.indexOf('과천') !== -1) {
      themeKeywords.push('과천');
    }
  }

  if (!themeKeywords.length) {
    return '정책 전반';
  }

  return themeKeywords.slice(0, 2).join('·');
}

function buildThemeLabelFromKey_(themeKey) {
  return themeKey === '정책 전반' ? '정책 전반' : themeKey + ' 관련 보도';
}

function getFreshnessBoost_(record) {
  var timestamp = getRecordTime_(record);

  if (!timestamp) {
    return 0;
  }

  var ageHours = (new Date().getTime() - timestamp.getTime()) / (1000 * 60 * 60);

  if (ageHours <= 6) {
    return 4;
  }
  if (ageHours <= 24) {
    return 2;
  }
  if (ageHours <= 36) {
    return 1;
  }
  return 0;
}

function hasNegativeSignal_(record, config) {
  var text = normalizeTextLower_(record.title + ' ' + record.summary);
  var rules = getKeywordRulesByBuckets_(config, ['negative_signal']);

  return rules.some(function(rule) {
    return rule.keyword && text.indexOf(normalizeTextLower_(rule.keyword)) !== -1;
  });
}

function isOpinionItem_(record, config) {
  var text = normalizeTextLower_(record.title);
  var rules = getKeywordRulesByBuckets_(config, ['opinion_signal']);

  return rules.some(function(rule) {
    return rule.keyword && text.indexOf(normalizeTextLower_(rule.keyword)) !== -1;
  });
}

function compareProcessedRecords_(left, right) {
  var scoreDiff = Number(right.importance_score || 0) - Number(left.importance_score || 0);

  if (scoreDiff !== 0) {
    return scoreDiff;
  }

  var leftTime = getRecordTime_(left);
  var rightTime = getRecordTime_(right);
  var leftValue = leftTime ? leftTime.getTime() : 0;
  var rightValue = rightTime ? rightTime.getTime() : 0;

  return rightValue - leftValue;
}

function isWithinLookback_(record, lookbackStart) {
  var timestamp = getRecordTime_(record);

  if (!timestamp) {
    return true;
  }

  return timestamp.getTime() >= lookbackStart.getTime();
}

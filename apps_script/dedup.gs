function deduplicateNews() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
  var rawRecords = readSheetRecords_(MM.SHEET_NAMES.RAW);

  if (!rawRecords.length) {
    overwriteSheetRecords_(MM.SHEET_NAMES.PROCESSED, MM.PROCESSED_COLUMNS, []);
    return 0;
  }

  var articles = rawRecords.map(function(record, index) {
    return {
      index: index,
      record: record,
      cleanLink: normalizeLink_(record.link),
      exactTitle: normalizeTextLower_(record.title),
      normalizedTitle: normalizeTitle(record.title),
      representativePriority: getRepresentativePriority_(record, config),
      timeValue: getRecordTime_(record)
    };
  });

  articles.sort(function(left, right) {
    if (right.representativePriority !== left.representativePriority) {
      return right.representativePriority - left.representativePriority;
    }

    var leftTime = left.timeValue ? left.timeValue.getTime() : 0;
    var rightTime = right.timeValue ? right.timeValue.getTime() : 0;
    return rightTime - leftTime;
  });

  var seenLinks = {};
  var seenTitles = {};
  var seenNormalizedTitles = {};
  var representatives = [];
  var representativeStats = {};

  articles.forEach(function(article) {
    var record = rawRecords[article.index];
    var duplicateInfo = null;

    record.normalized_title = article.normalizedTitle;
    record.duplicate_flag = 'representative';

    if (article.cleanLink && seenLinks[article.cleanLink] !== undefined) {
      duplicateInfo = { repIndex: seenLinks[article.cleanLink], reason: 'duplicate_link' };
    } else if (article.exactTitle && seenTitles[article.exactTitle] !== undefined) {
      duplicateInfo = { repIndex: seenTitles[article.exactTitle], reason: 'duplicate_exact_title' };
    } else if (article.normalizedTitle && seenNormalizedTitles[article.normalizedTitle] !== undefined) {
      duplicateInfo = { repIndex: seenNormalizedTitles[article.normalizedTitle], reason: 'duplicate_normalized_title' };
    } else {
      duplicateInfo = findFuzzyDuplicate_(article, representatives, config.dedup.fuzzyThreshold);
    }

    if (duplicateInfo) {
      var representativeRecord = rawRecords[duplicateInfo.repIndex];
      record.duplicate_flag = duplicateInfo.reason;
      record.notes = addNote_(
        record.notes,
        'representative=' + representativeRecord.source_name + ':' + limitText_(representativeRecord.title, 80)
      );

      if (!representativeStats[duplicateInfo.repIndex]) {
        representativeStats[duplicateInfo.repIndex] = { sources: {}, count: 1 };
      }

      representativeStats[duplicateInfo.repIndex].count += 1;
      representativeStats[duplicateInfo.repIndex].sources[record.source_name] = true;
      return;
    }

    if (!representativeStats[article.index]) {
      representativeStats[article.index] = { sources: {}, count: 1 };
    }

    representativeStats[article.index].sources[record.source_name] = true;
    representatives.push(article);

    if (article.cleanLink) {
      seenLinks[article.cleanLink] = article.index;
    }
    if (article.exactTitle) {
      seenTitles[article.exactTitle] = article.index;
    }
    if (article.normalizedTitle) {
      seenNormalizedTitles[article.normalizedTitle] = article.index;
    }
  });

  Object.keys(representativeStats).forEach(function(indexKey) {
    var record = rawRecords[Number(indexKey)];
    var stat = representativeStats[indexKey];
    var sourceNames = Object.keys(stat.sources);

    record.notes = upsertTaggedNote_(record.notes, 'duplicate_count', String(stat.count - 1));
    if (sourceNames.length > 1) {
      record.notes = upsertTaggedNote_(record.notes, 'duplicate_sources', sourceNames.join(', '));
    }
  });

  overwriteSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, rawRecords);

  var processedRecords = rawRecords.filter(isRepresentativeRecord_).map(function(record) {
    var output = cloneObject_(record);
    output.rank = '';
    return output;
  });

  overwriteSheetRecords_(MM.SHEET_NAMES.PROCESSED, MM.PROCESSED_COLUMNS, processedRecords);
  return processedRecords.length;
}

function normalizeTitle(title) {
  var text = String(title || '').toLowerCase();

  text = text
    .replace(/\[[^\]]*\]/g, ' ')
    .replace(/\([^)]+\)/g, ' ')
    .replace(/【[^】]*】/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/(?:\||-|–|—|\/)\s*(연합뉴스|뉴스1|뉴시스|매일경제|한국경제|서울경제|이데일리|머니투데이)\s*$/g, ' ')
    .replace(/\b(종합|속보|단독|사진|영상|인터뷰)\b/g, ' ')
    .replace(/[!"#$%&'*+,./:;<=>?@\\^_`{|}~·…ㆍ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  return text;
}

function normalizeLink_(link) {
  var value = String(link || '').trim();

  if (!value) {
    return '';
  }

  value = value.split('#')[0];
  value = value.split('?')[0];
  value = value.replace(/\/+$/, '');
  return value.toLowerCase();
}

function getRepresentativePriority_(record, config) {
  var priority = getSourcePriority_(record.source_name, config);

  if (String(record.source_type || '').toLowerCase() === 'rss') {
    priority += 10;
  }

  if (String(record.source_type || '').toLowerCase() === 'google_news') {
    priority += 2;
  }

  return priority;
}

function findFuzzyDuplicate_(article, representatives, threshold) {
  if (!article.normalizedTitle) {
    return null;
  }

  for (var index = 0; index < representatives.length; index += 1) {
    var representative = representatives[index];
    var similarity = titleSimilarity_(article.normalizedTitle, representative.normalizedTitle);

    if (similarity >= Number(threshold || 0.84)) {
      return {
        repIndex: representative.index,
        reason: 'duplicate_fuzzy_title_' + similarity.toFixed(2)
      };
    }
  }

  return null;
}

function titleSimilarity_(leftTitle, rightTitle) {
  var left = normalizeTitle(leftTitle);
  var right = normalizeTitle(rightTitle);

  if (!left || !right) {
    return 0;
  }

  if (left === right) {
    return 1;
  }

  if ((left.length > 12 && left.indexOf(right) !== -1) || (right.length > 12 && right.indexOf(left) !== -1)) {
    return 0.92;
  }

  var leftTokens = left.split(' ').filter(function(token) { return token; });
  var rightTokens = right.split(' ').filter(function(token) { return token; });

  if (!leftTokens.length || !rightTokens.length) {
    return 0;
  }

  var tokenMap = {};
  var intersection = 0;

  leftTokens.forEach(function(token) {
    tokenMap[token] = true;
  });

  rightTokens.forEach(function(token) {
    if (tokenMap[token]) {
      intersection += 1;
    }
  });

  var union = leftTokens.length + rightTokens.length - intersection;
  return union ? intersection / union : 0;
}

function scorePolicyRelevance() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
  var rawRecords = readSheetRecords_(MM.SHEET_NAMES.RAW);
  var rules = getKeywordRulesByBuckets_(config, ['topic', 'phrase']);

  rawRecords.forEach(function(record) {
    var scoreResult = calculatePolicyScore_(record, rules, config);
    record.policy_score = scoreResult.score;
    record.keyword = scoreResult.keywords.join(', ');
    record.notes = upsertTaggedNote_(record.notes, 'policy_hits', scoreResult.keywords.join('|'));
  });

  overwriteSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, rawRecords);
  return rawRecords.length;
}

function calculatePolicyScore_(record, rules, config) {
  var titleText = normalizeTextLower_(record.title);
  var summaryText = normalizeTextLower_(record.summary);
  var matchedKeywords = [];
  var matchedLookup = {};
  var score = 0;

  rules.forEach(function(rule) {
    if (rule.enabled === false) {
      return;
    }

    var keyword = normalizeTextLower_(rule.keyword);
    if (!keyword) {
      return;
    }

    var inTitle = titleText.indexOf(keyword) !== -1;
    var inSummary = summaryText.indexOf(keyword) !== -1;

    if (!inTitle && !inSummary) {
      return;
    }

    if (!matchedLookup[rule.keyword]) {
      matchedLookup[rule.keyword] = true;
      matchedKeywords.push(rule.keyword);
    }

    if (inTitle) {
      score += Number(rule.weight || 1) * Number(config.scoring.titleWeight || 3);
    } else if (inSummary) {
      score += Number(rule.weight || 1) * Number(config.scoring.summaryWeight || 1);
    }

    if (rule.bucket === 'phrase') {
      score += Number(config.scoring.phraseBonus || 0);
    }
  });

  if (score > 0) {
    score += getSourcePriority_(record.source_name, config);
  }

  return {
    score: Math.round(score * 10) / 10,
    keywords: matchedKeywords
  };
}

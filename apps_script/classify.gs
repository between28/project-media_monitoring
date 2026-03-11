function classifyFrames() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
  var rawRecords = readSheetRecords_(MM.SHEET_NAMES.RAW);

  rawRecords.forEach(function(record) {
    var result = classifyFrameForRecord_(record, config);
    record.frame_category = result.category;
    record.notes = upsertTaggedNote_(record.notes, 'frame_hits', result.hits.join('|'));
  });

  overwriteSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, rawRecords);
  return rawRecords.length;
}

function classifyFrameForRecord_(record, config) {
  var text = normalizeTextLower_(record.title + ' ' + record.summary);
  var frameDefinitions = [
    { bucket: 'frame_policy', category: '정책 설명' },
    { bucket: 'frame_positive', category: '긍정 평가' },
    { bucket: 'frame_critical', category: '비판 / 우려' },
    { bucket: 'frame_political', category: '정치 / 기관 이슈' }
  ];
  var scores = {
    '정책 설명': 0,
    '긍정 평가': 0,
    '비판 / 우려': 0,
    '정치 / 기관 이슈': 0
  };
  var hits = [];

  frameDefinitions.forEach(function(definition) {
    var rules = getKeywordRulesByBuckets_(config, [definition.bucket]);
    rules.forEach(function(rule) {
      var keyword = normalizeTextLower_(rule.keyword);
      if (!keyword) {
        return;
      }

      if (text.indexOf(keyword) !== -1) {
        scores[definition.category] += Number(rule.weight || 1);
        hits.push(definition.bucket + ':' + rule.keyword);
      }
    });
  });

  var orderedCategories = ['비판 / 우려', '정치 / 기관 이슈', '긍정 평가', '정책 설명'];
  var selectedCategory = '기타';
  var selectedScore = 0;

  orderedCategories.forEach(function(category) {
    if (scores[category] > selectedScore) {
      selectedCategory = category;
      selectedScore = scores[category];
    }
  });

  if (selectedScore === 0 && Number(record.policy_score || 0) >= Number(config.scoring.highRelevanceThreshold || 6)) {
    selectedCategory = '정책 설명';
  }

  return {
    category: selectedCategory,
    hits: hits
  };
}

function initializeProject() {
  ensureOperationalSheets();
  return 'MOLIT media monitoring MVP initialized.';
}

function resetConfigSourcesSheet() {
  ensureOperationalSheets();
  overwriteSheetRecords_(MM.SHEET_NAMES.SOURCES, MM.SOURCE_COLUMNS, MM.DEFAULT_CONFIG.sources);
  resetConfigCache_();
  return 'config_sources reset with ' + MM.DEFAULT_CONFIG.sources.length + ' source rows.';
}

function resetConfigRuntimeSheet() {
  ensureOperationalSheets();
  overwriteSheetRecords_(MM.SHEET_NAMES.RUNTIME, MM.RUNTIME_COLUMNS, MM.DEFAULT_RUNTIME_SETTINGS);
  resetConfigCache_();
  return 'config_runtime reset with ' + MM.DEFAULT_RUNTIME_SETTINGS.length + ' runtime rows.';
}

function resetConfigKeywordsSheet() {
  ensureOperationalSheets();
  overwriteSheetRecords_(MM.SHEET_NAMES.KEYWORDS, MM.KEYWORD_COLUMNS, MM.DEFAULT_CONFIG.keywordRules);
  resetConfigCache_();
  return 'config_keywords reset with ' + MM.DEFAULT_CONFIG.keywordRules.length + ' keyword rows.';
}

function clearMonitoringData() {
  ensureOperationalSheets();
  overwriteSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, []);
  overwriteSheetRecords_(MM.SHEET_NAMES.PROCESSED, MM.PROCESSED_COLUMNS, []);
  overwriteSheetRecords_(MM.SHEET_NAMES.BRIEFING, MM.BRIEFING_COLUMNS, []);
  return 'Cleared news_raw, news_processed, briefing_output.';
}

function runCollectionOnly() {
  ensureOperationalSheets();
  resetConfigCache_();

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    return collectRSS();
  } finally {
    lock.releaseLock();
  }
}

function runAnalysisAndBriefing() {
  ensureOperationalSheets();
  resetConfigCache_();

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    deduplicateNews();
    scorePolicyRelevance();
    fetchArticleBodies();
    scorePolicyRelevance();
    classifyFrames();
    rankArticles();
    return generateBriefing();
  } finally {
    lock.releaseLock();
  }
}

function runDailyMonitoring() {
  var collectedCount = runCollectionOnly();
  var briefingText = runAnalysisAndBriefing();
  return 'Collected ' + collectedCount + ' items.\n\n' + briefingText;
}

function runAnalysisOnly() {
  return runAnalysisAndBriefing();
}

function setupDailyTrigger() {
  var triggers = ScriptApp.getProjectTriggers();

  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'runDailyMonitoring') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger('runDailyMonitoring')
    .timeBased()
    .atHour(5)
    .nearMinute(30)
    .everyDays(1)
    .create();

  return 'Daily trigger created near 05:30.';
}

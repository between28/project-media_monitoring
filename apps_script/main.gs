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

function runDailyMonitoring() {
  ensureOperationalSheets();
  resetConfigCache_();

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    collectRSS();
    deduplicateNews();
    scorePolicyRelevance();
    classifyFrames();
    rankArticles();
    return generateBriefing();
  } finally {
    lock.releaseLock();
  }
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

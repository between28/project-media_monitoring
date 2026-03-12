function initializeProject() {
  ensureOperationalSheets();
  return 'MOLIT media monitoring MVP initialized.';
}

function getDefaultCollectionTriggerSlots_() {
  return [
    { hour: 0, minute: 15 },
    { hour: 3, minute: 15 },
    { hour: 5, minute: 0 },
    { hour: 12, minute: 15 },
    { hour: 18, minute: 15 },
    { hour: 21, minute: 15 }
  ];
}

function getDefaultBriefingTriggerSlot_() {
  return { hour: 5, minute: 30 };
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
  return setupSeparatedTriggers();
}

function setupCollectionTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  var slots = getDefaultCollectionTriggerSlots_();

  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'runCollectionOnly' ||
        trigger.getHandlerFunction() === 'runDailyMonitoring') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  slots.forEach(function(slot) {
    createDailyTimeTrigger_('runCollectionOnly', slot.hour, slot.minute);
  });

  return 'Collection triggers created near ' + slots.map(function(slot) {
    return formatTriggerSlot_(slot);
  }).join(', ') + '.';
}

function setupBriefingTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  var slot = getDefaultBriefingTriggerSlot_();

  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'runAnalysisAndBriefing' ||
        trigger.getHandlerFunction() === 'runAnalysisOnly' ||
        trigger.getHandlerFunction() === 'runDailyMonitoring') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  createDailyTimeTrigger_('runAnalysisAndBriefing', slot.hour, slot.minute);
  return 'Briefing trigger created near ' + formatTriggerSlot_(slot) + '.';
}

function setupSeparatedTriggers() {
  var collectionResult = setupCollectionTriggers();
  var briefingResult = setupBriefingTrigger();
  return collectionResult + '\n' + briefingResult;
}

function createDailyTimeTrigger_(handlerName, hour, minute) {
  ScriptApp.newTrigger(handlerName)
    .timeBased()
    .atHour(hour)
    .nearMinute(minute)
    .everyDays(1)
    .create();
}

function formatTriggerSlot_(slot) {
  var hour = slot.hour < 10 ? '0' + slot.hour : String(slot.hour);
  var minute = slot.minute < 10 ? '0' + slot.minute : String(slot.minute);
  return hour + ':' + minute;
}

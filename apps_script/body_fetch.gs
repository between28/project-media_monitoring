function fetchArticleBodies() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
  var rawRecords = readSheetRecords_(MM.SHEET_NAMES.RAW);

  if (!rawRecords.length) {
    return 0;
  }

  var analysisNow = getAnalysisNow_(config);
  var lookbackStart = getLookbackStart_(config, analysisNow);
  var candidates = rawRecords.map(function(record, index) {
    return {
      index: index,
      record: record,
      recordTime: getRecordTime_(record),
      sourcePriority: getSourcePriority_(record.source_name, config)
    };
  }).filter(function(item) {
    return isBodyFetchCandidate_(item.record, config, lookbackStart);
  }).sort(compareBodyFetchCandidates_);

  var limit = Number(config.collection.maxBodyFetchCandidates || 12);
  var fetchedCount = 0;
  var updatedCount = 0;

  candidates.slice(0, limit).forEach(function(candidate) {
    fetchedCount += 1;

    try {
      var bodyText = fetchArticleBodyText_(candidate.record, config);
      if (!bodyText) {
        return;
      }

      candidate.record.body_text = bodyText;
      candidate.record.notes = upsertTaggedNote_(candidate.record.notes, 'body_fetched', 'true');
      updatedCount += 1;
    } catch (error) {
      candidate.record.notes = upsertTaggedNote_(candidate.record.notes, 'body_fetch_error', limitText_(error.message, 80));
      Logger.log('Body fetch failed for ' + candidate.record.source_name + ': ' + error.message);
    }
  });

  overwriteSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, rawRecords);
  Logger.log('Body fetch updated ' + updatedCount + ' of ' + fetchedCount + ' candidate articles.');
  return updatedCount;
}

function isBodyFetchCandidate_(record, config, lookbackStart) {
  var analysisNow = getAnalysisNow_(config);

  if (!isRepresentativeRecord_(record)) {
    return false;
  }

  if (!record.link || !isWithinLookback_(record, lookbackStart, analysisNow)) {
    return false;
  }

  if (record.body_text) {
    return false;
  }

  if (String(record.source_type || '').toLowerCase() === 'google_news' &&
      !toBoolean_((config.collection || {}).fetchBodyFromGoogleNews)) {
    return false;
  }

  return Number(record.policy_score || 0) >= Number(config.collection.bodyFetchMinimumPolicyScore || 4);
}

function compareBodyFetchCandidates_(left, right) {
  var scoreDiff = Number(right.record.policy_score || 0) - Number(left.record.policy_score || 0);
  if (scoreDiff !== 0) {
    return scoreDiff;
  }

  if (right.sourcePriority !== left.sourcePriority) {
    return right.sourcePriority - left.sourcePriority;
  }

  var leftTime = left.recordTime ? left.recordTime.getTime() : 0;
  var rightTime = right.recordTime ? right.recordTime.getTime() : 0;
  return rightTime - leftTime;
}

function fetchArticleBodyText_(record, config) {
  var response = UrlFetchApp.fetch(record.link, {
    muteHttpExceptions: true,
    followRedirects: true,
    headers: {
      'User-Agent': 'Mozilla/5.0 (Apps Script Article Body Fetcher)'
    }
  });

  if (response.getResponseCode() >= 400) {
    throw new Error('HTTP ' + response.getResponseCode());
  }

  var html = response.getContentText();
  if (!looksLikeHtml_(html)) {
    throw new Error('Article URL returned non-HTML response');
  }

  return extractArticleBodyText_(html, config);
}

function looksLikeHtml_(html) {
  var text = String(html || '').replace(/^\uFEFF/, '').trim().toLowerCase();
  return text.indexOf('<html') !== -1 || text.indexOf('<body') !== -1 || text.indexOf('<article') !== -1;
}

function extractArticleBodyText_(html, config) {
  var text = String(html || '');
  var candidates = [];
  var articleMatches = text.match(/<article\b[\s\S]*?<\/article>/gi) || [];
  var mainMatches = text.match(/<main\b[\s\S]*?<\/main>/gi) || [];
  var bodyMatches = text.match(/<body\b[\s\S]*?<\/body>/gi) || [];

  candidates = candidates.concat(articleMatches, mainMatches);
  if (!candidates.length && bodyMatches.length) {
    candidates.push(bodyMatches[0]);
  }
  if (!candidates.length) {
    candidates.push(text);
  }

  var bestText = '';

  candidates.forEach(function(candidateHtml) {
    var cleaned = stripArticleChrome_(candidateHtml);
    var plainText = stripHtml_(cleaned);

    if (plainText.length > bestText.length) {
      bestText = plainText;
    }
  });

  bestText = collapseWhitespace_(bestText);
  if (!bestText) {
    return '';
  }

  return limitText_(bestText, Number(config.collection.bodyTextMaxLength || 4000));
}

function stripArticleChrome_(html) {
  return String(html || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
    .replace(/<svg[\s\S]*?<\/svg>/gi, ' ')
    .replace(/<form[\s\S]*?<\/form>/gi, ' ')
    .replace(/<header[\s\S]*?<\/header>/gi, ' ')
    .replace(/<footer[\s\S]*?<\/footer>/gi, ' ')
    .replace(/<nav[\s\S]*?<\/nav>/gi, ' ')
    .replace(/<aside[\s\S]*?<\/aside>/gi, ' ')
    .replace(/<button[\s\S]*?<\/button>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ');
}

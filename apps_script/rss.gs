function collectRSS() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
  var policyRules = getKeywordRulesByBuckets_(config, ['topic', 'phrase']);
  var analysisNow = getAnalysisNow_(config);
  var lookbackStart = getLookbackStart_(config, analysisNow);
  var activeSources = (config.sources || []).filter(function(source) {
    return source.enabled;
  });
  var collectedTime = formatDateTime_(new Date(), config.timezone);
  var collectedRecords = [];

  activeSources.forEach(function(source) {
    var feedUrl = resolveFeedUrl_(source);

    if (!feedUrl) {
      return;
    }

    try {
      var maxItemsForSource = getMaxItemsForSource_(source, config);
      var response = UrlFetchApp.fetch(feedUrl, {
        muteHttpExceptions: true,
        followRedirects: true,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Apps Script RSS Collector)'
        }
      });

      if (response.getResponseCode() >= 400) {
        throw new Error('HTTP ' + response.getResponseCode());
      }

      var responseText = response.getContentText();
      if (!looksLikeFeedXml_(responseText)) {
        throw new Error('Non-feed response returned by source URL');
      }

      var items = parseSourceItems_(responseText, source, maxItemsForSource);
      var keptCount = 0;
      var droppedByRelevanceCount = 0;
      var droppedByDateCount = 0;

      items.forEach(function(item) {
        if (!shouldCollectItem_(item, source, policyRules, config)) {
          droppedByRelevanceCount += 1;
          return;
        }

        if (!shouldKeepItemInCollectionWindow_(item, collectedTime, lookbackStart, analysisNow)) {
          droppedByDateCount += 1;
          return;
        }

        keptCount += 1;
        collectedRecords.push({
          collected_time: collectedTime,
          publish_time: item.publish_time || collectedTime,
          source_type: source.source_type,
          source_name: source.source_name,
          category_group: source.category_group,
          title: item.title,
          link: item.link,
          summary: item.summary,
          keyword: '',
          duplicate_flag: '',
          normalized_title: '',
          policy_score: 0,
          frame_category: '',
          importance_score: 0,
          language: item.language,
          notes: addNote_(
            addNote_('', source.keyword ? 'source_keyword=' + source.keyword : ''),
            'feed=' + limitText_(feedUrl, 180)
          ),
          body_text: ''
        });
      });

      Logger.log(
        'Collected ' + keptCount +
        ' items from ' + source.source_name +
        ' after prefilter/window; dropped ' +
        droppedByRelevanceCount +
        ' by relevance and ' +
        droppedByDateCount +
        ' by date.'
      );
    } catch (error) {
      Logger.log('RSS fetch failed for ' + source.source_name + ': ' + error.message);
    }
  });

  appendSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, collectedRecords);
  return collectedRecords.length;
}

function getMaxItemsForSource_(source, config) {
  if (source.source_type === 'google_news') {
    return Number(config.collection.maxItemsPerGoogleNewsFeed || config.collection.maxItemsPerFeed || 10);
  }

  return Number(config.collection.maxItemsPerFeed || 10);
}

function shouldCollectItem_(item, source, policyRules, config) {
  var previewRecord = {
    title: item.title,
    summary: item.summary,
    source_name: source.source_name
  };
  var scoreResult = calculatePolicyScore_(previewRecord, policyRules, config);
  var hitStats = getPolicyHitStatsFromKeywords_(scoreResult.keywords, config);

  if (hitStats.phraseHits > 0) {
    return true;
  }

  if (hitStats.totalHits < Number(config.collection.rawMinimumKeywordHits || 2)) {
    return false;
  }

  return hasCollectionCoreKeyword_(scoreResult.keywords, config);
}

function shouldKeepItemInCollectionWindow_(item, collectedTime, lookbackStart, analysisNow) {
  var timestamp = parseDateValue_(item.publish_time || collectedTime);

  if (!timestamp) {
    return false;
  }

  return timestamp.getTime() >= lookbackStart.getTime() &&
    timestamp.getTime() <= analysisNow.getTime();
}

function hasCollectionCoreKeyword_(keywords, config) {
  var lookup = {};

  (config.collection.rawCoreKeywords || []).forEach(function(keyword) {
    lookup[normalizeTextLower_(keyword)] = true;
  });

  return keywords.some(function(keyword) {
    return lookup[normalizeTextLower_(keyword)] === true;
  });
}

function parseSourceItems_(xmlText, source, maxItems) {
  var document = XmlService.parse(xmlText);
  var root = document.getRootElement();
  var rootName = root.getName();
  var limit = Number(maxItems || 15);

  if (rootName === 'urlset' || rootName === 'sitemapindex') {
    return parseSitemapItems_(document, source, limit, 1);
  }

  return parseFeedItemsFromDocument_(document, limit);
}

function parseFeedItemsFromDocument_(document, maxItems) {
  var root = document.getRootElement();
  var items = [];
  var limit = Number(maxItems || 10);

  if (root.getName() === 'rss' || root.getName() === 'RDF') {
    var channel = root.getChild('channel') || root;
    var rssItems = channel.getChildren('item').slice(0, limit);
    items = rssItems.map(function(item) {
      return parseRssItem_(item);
    });
  } else if (root.getName() === 'feed') {
    var namespace = root.getNamespace();
    var atomEntries = root.getChildren('entry', namespace).slice(0, limit);
    items = atomEntries.map(function(entry) {
      return parseAtomEntry_(entry);
    });
  }

  return items.filter(function(item) {
    return item.title && item.link;
  }).slice(0, limit);
}

function parseSitemapItems_(document, source, maxItems, remainingDepth) {
  var root = document.getRootElement();
  var rootName = root.getName();

  if (rootName === 'sitemapindex') {
    return parseNestedSitemapItems_(root, source, maxItems, remainingDepth);
  }

  if (rootName !== 'urlset') {
    return [];
  }

  return getChildrenByName_(root, 'url').slice(0, Number(maxItems || 10)).map(function(item) {
    return parseSitemapUrl_(item);
  }).filter(function(item) {
    return item.title && item.link;
  }).slice(0, Number(maxItems || 10));
}

function parseNestedSitemapItems_(root, source, maxItems, remainingDepth) {
  if (!remainingDepth) {
    return [];
  }

  var sitemapNodes = getChildrenByName_(root, 'sitemap');
  var items = [];

  sitemapNodes.some(function(node) {
    var nestedUrl = getElementTextByNames_(node, ['loc']);
    if (!nestedUrl) {
      return false;
    }

    try {
      var response = UrlFetchApp.fetch(nestedUrl, {
        muteHttpExceptions: true,
        followRedirects: true,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Apps Script RSS Collector)'
        }
      });

      if (response.getResponseCode() >= 400) {
        throw new Error('HTTP ' + response.getResponseCode());
      }

      var responseText = response.getContentText();
      if (!looksLikeFeedXml_(responseText)) {
        throw new Error('Nested sitemap returned non-feed response');
      }

      items = items.concat(parseSitemapItems_(
        XmlService.parse(responseText),
        source,
        maxItems - items.length,
        remainingDepth - 1
      ));
    } catch (error) {
      Logger.log('Nested sitemap fetch failed for ' + source.source_name + ': ' + error.message);
    }

    return items.length >= maxItems;
  });

  return items.slice(0, maxItems);
}

function parseSitemapUrl_(item) {
  var link = collapseWhitespace_(getElementTextByNames_(item, ['loc']));
  var lastmodText = getElementTextByNames_(item, ['lastmod']);
  var newsNode = getFirstChildByName_(item, 'news');
  var title = newsNode ? getElementTextByNames_(newsNode, ['title']) : '';
  var keywordSummary = newsNode ? getElementTextByNames_(newsNode, ['keywords']) : '';
  var publishText = newsNode ? getElementTextByNames_(newsNode, ['publication_date']) : '';
  var publishDate = parseDateValue_(publishText || lastmodText);
  var normalizedTitle = collapseWhitespace_(title || deriveTitleFromUrl_(link));
  var summary = limitText_(stripHtml_(keywordSummary), 600);

  return {
    title: normalizedTitle,
    link: link,
    publish_time: publishDate ? formatDateTime_(publishDate, getMonitoringConfig().timezone) : '',
    summary: summary,
    language: detectLanguage_(normalizedTitle + ' ' + summary)
  };
}

function parseRssItem_(item) {
  var title = getElementTextByNames_(item, ['title']);
  var link = extractFeedLink_(item);
  var publishText = getElementTextByNames_(item, ['pubDate', 'date', 'published', 'updated']);
  var summary = stripHtml_(getElementTextByNames_(item, ['description', 'summary', 'encoded', 'content']));
  var publishDate = parseDateValue_(publishText);

  return {
    title: collapseWhitespace_(title),
    link: collapseWhitespace_(link),
    publish_time: publishDate ? formatDateTime_(publishDate, getMonitoringConfig().timezone) : '',
    summary: limitText_(summary, 600),
    language: detectLanguage_(title + ' ' + summary)
  };
}

function parseAtomEntry_(entry) {
  var title = getElementTextByNames_(entry, ['title']);
  var link = extractFeedLink_(entry);
  var publishText = getElementTextByNames_(entry, ['published', 'updated']);
  var summary = stripHtml_(getElementTextByNames_(entry, ['summary', 'content']));
  var publishDate = parseDateValue_(publishText);

  return {
    title: collapseWhitespace_(title),
    link: collapseWhitespace_(link),
    publish_time: publishDate ? formatDateTime_(publishDate, getMonitoringConfig().timezone) : '',
    summary: limitText_(summary, 600),
    language: detectLanguage_(title + ' ' + summary)
  };
}

function extractFeedLink_(element) {
  var children = element.getChildren();

  for (var index = 0; index < children.length; index += 1) {
    if (children[index].getName() !== 'link') {
      continue;
    }

    var href = children[index].getAttribute('href');
    if (href && href.getValue()) {
      return href.getValue();
    }

    if (children[index].getText()) {
      return children[index].getText();
    }
  }

  return '';
}

function getElementTextByNames_(element, names) {
  var wanted = {};
  var children = element.getChildren();

  names.forEach(function(name) {
    wanted[name] = true;
  });

  for (var index = 0; index < children.length; index += 1) {
    if (wanted[children[index].getName()]) {
      return children[index].getText();
    }
  }

  return '';
}

function getChildrenByName_(element, name) {
  return element.getChildren().filter(function(child) {
    return child.getName() === name;
  });
}

function getFirstChildByName_(element, name) {
  var matches = getChildrenByName_(element, name);
  return matches.length ? matches[0] : null;
}

function deriveTitleFromUrl_(url) {
  var value = String(url || '').replace(/[?#].*$/, '');
  if (!value) {
    return '';
  }

  var lastSegment = value.split('/').pop();
  try {
    return decodeURIComponent(lastSegment || '').replace(/[-_]+/g, ' ');
  } catch (error) {
    return String(lastSegment || '').replace(/[-_]+/g, ' ');
  }
}

function looksLikeFeedXml_(responseText) {
  var text = String(responseText || '').replace(/^\uFEFF/, '').trim().toLowerCase();
  return text.indexOf('<rss') !== -1 ||
    text.indexOf('<feed') !== -1 ||
    text.indexOf('<rdf:rdf') !== -1 ||
    text.indexOf('<urlset') !== -1 ||
    text.indexOf('<sitemapindex') !== -1;
}

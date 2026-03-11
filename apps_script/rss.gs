function collectRSS() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
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

      var items = parseSourceItems_(responseText, source, config.collection.maxItemsPerFeed);

      items.forEach(function(item) {
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
          )
        });
      });
    } catch (error) {
      Logger.log('RSS fetch failed for ' + source.source_name + ': ' + error.message);
    }
  });

  appendSheetRecords_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS, collectedRecords);
  return collectedRecords.length;
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

  if (root.getName() === 'rss' || root.getName() === 'RDF') {
    var channel = root.getChild('channel') || root;
    var rssItems = channel.getChildren('item');
    items = rssItems.map(function(item) {
      return parseRssItem_(item);
    });
  } else if (root.getName() === 'feed') {
    var namespace = root.getNamespace();
    var atomEntries = root.getChildren('entry', namespace);
    items = atomEntries.map(function(entry) {
      return parseAtomEntry_(entry);
    });
  }

  return items.filter(function(item) {
    return item.title && item.link;
  }).slice(0, Number(maxItems || 15));
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

  return getChildrenByName_(root, 'url').map(function(item) {
    return parseSitemapUrl_(item);
  }).filter(function(item) {
    return item.title && item.link;
  }).slice(0, Number(maxItems || 15));
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

var MM = MM || {};

MM.SHEET_NAMES = {
  RAW: 'news_raw',
  PROCESSED: 'news_processed',
  BRIEFING: 'briefing_output',
  SOURCES: 'config_sources',
  KEYWORDS: 'config_keywords',
  RUNTIME: 'config_runtime'
};

MM.RAW_COLUMNS = [
  'collected_time',
  'publish_time',
  'source_type',
  'source_name',
  'category_group',
  'title',
  'link',
  'summary',
  'keyword',
  'duplicate_flag',
  'normalized_title',
  'policy_score',
  'frame_category',
  'importance_score',
  'language',
  'notes',
  'body_text'
];

MM.PROCESSED_COLUMNS = ['rank'].concat(MM.RAW_COLUMNS);

MM.BRIEFING_COLUMNS = [
  'generated_time',
  'topic_name',
  'section_name',
  'content',
  'supporting_articles',
  'notes'
];

MM.SOURCE_COLUMNS = [
  'enabled',
  'source_name',
  'source_type',
  'category_group',
  'feed_url',
  'keyword',
  'notes'
];

MM.KEYWORD_COLUMNS = [
  'enabled',
  'bucket',
  'keyword',
  'weight',
  'notes'
];

MM.RUNTIME_COLUMNS = [
  'key',
  'value',
  'notes'
];

MM.DEFAULT_CONFIG = {
  timezone: 'Asia/Seoul',
  topic: {
    name: '도심 주택공급 확대 및 신속화 방안',
    announcementDate: '2026-01-29',
    announcementDateTime: '2026-01-29T10:00:00+09:00'
  },
  analysis: {
    referenceTime: ''
  },
  collection: {
    maxItemsPerFeed: 10,
    maxItemsPerGoogleNewsFeed: 8,
    reportLookbackHours: 36,
    maxProcessedRows: 50,
    maxBriefingArticles: 12,
    maxThemes: 3,
    rawMinimumKeywordHits: 2,
    rawCoreKeywords: ['공급', '신속화', '국토부', '용산', '태릉', '과천'],
    maxBodyFetchCandidates: 12,
    bodyFetchMinimumPolicyScore: 4,
    fetchBodyFromGoogleNews: false,
    bodyTextMaxLength: 4000
  },
  dedup: {
    fuzzyThreshold: 0.84
  },
  scoring: {
    titleWeight: 3,
    summaryWeight: 1,
    bodyWeight: 0.75,
    phraseBonus: 3,
    highRelevanceThreshold: 8,
    minimumKeywordHits: 2
  },
  ranking: {
    majorOutletBoost: 4,
    criticalFrameBoost: 2,
    opinionBoost: 3,
    repeatedNarrativeBonus: 1
  },
  genericThemeKeywords: ['도심', '주택', '공급', '신속화', '국토부', '주택공급', '확대'],
  sourcePriority: {
    '연합뉴스': 4,
    '뉴스1': 3,
    '뉴시스': 3,
    '매일경제': 3,
    '한국경제': 3,
    '서울경제': 3,
    '이데일리': 2,
    '아시아경제': 2,
    '머니투데이': 2,
    '조선일보': 2,
    '중앙일보': 2,
    '동아일보': 2,
    '한겨레': 2,
    '경향신문': 2,
    '서울신문': 2,
    '세계일보': 2,
    'KBS': 3,
    'MBC': 3,
    'SBS': 3,
    'YTN': 3,
    'JTBC': 2,
    '노컷뉴스': 2,
    '헤럴드경제': 2,
    '파이낸셜뉴스': 2,
    '오마이뉴스': 1,
    '프레시안': 1,
    '데일리안': 1,
    '국토일보': 1,
    '건설경제': 1
  },
  sources: [
    {
      enabled: true,
      source_name: 'Google News - 도심 주택공급 확대',
      source_type: 'google_news',
      category_group: 'policy_keyword',
      feed_url: '',
      keyword: '도심 주택공급 확대',
      notes: 'default topic expansion query'
    },
    {
      enabled: true,
      source_name: 'Google News - 도심 주택공급 신속화',
      source_type: 'google_news',
      category_group: 'policy_keyword',
      feed_url: '',
      keyword: '도심 주택공급 신속화',
      notes: 'default topic expansion query'
    },
    {
      enabled: true,
      source_name: 'Google News - 1.29 공급대책',
      source_type: 'google_news',
      category_group: 'policy_keyword',
      feed_url: '',
      keyword: '1.29 공급대책',
      notes: 'default topic expansion query'
    },
    {
      enabled: true,
      source_name: 'Google News - 국토부 주택공급 확대',
      source_type: 'google_news',
      category_group: 'policy_keyword',
      feed_url: '',
      keyword: '국토부 주택공급 확대',
      notes: 'default topic expansion query'
    },
    {
      enabled: true,
      source_name: 'Google News - 용산 국제업무지구 공급',
      source_type: 'google_news',
      category_group: 'policy_keyword',
      feed_url: '',
      keyword: '용산 국제업무지구 공급',
      notes: 'default topic expansion query'
    },
    {
      enabled: true,
      source_name: 'Google News - 태릉CC 공급',
      source_type: 'google_news',
      category_group: 'policy_keyword',
      feed_url: '',
      keyword: '태릉CC 공급',
      notes: 'default topic expansion query'
    },
    {
      enabled: true,
      source_name: 'Google News - 과천 경마장 공급',
      source_type: 'google_news',
      category_group: 'policy_keyword',
      feed_url: '',
      keyword: '과천 경마장 공급',
      notes: 'default topic expansion query'
    },
    {
      enabled: true,
      source_name: 'Google News - 뉴스1',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '뉴스1 도심 주택공급 확대',
      notes: 'backup query for missing direct RSS'
    },
    {
      enabled: false,
      source_name: 'Google News - 뉴시스',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '뉴시스 도심 주택공급 확대',
      notes: 'disabled by default after direct section RSS was added on 2026-03-11'
    },
    {
      enabled: false,
      source_name: 'Google News - 조선일보',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '조선일보 1.29 공급대책',
      notes: 'disabled by default after direct RSS was restored on 2026-03-11'
    },
    {
      enabled: true,
      source_name: 'Google News - 중앙일보',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '중앙일보 1.29 공급대책',
      notes: 'backup query for missing direct RSS'
    },
    {
      enabled: false,
      source_name: 'Google News - 서울경제',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '서울경제 국토부 주택공급 확대',
      notes: 'disabled by default after section RSS was added on 2026-03-11'
    },
    {
      enabled: false,
      source_name: 'Google News - 아시아경제',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '아시아경제 도심 주택공급 신속화',
      notes: 'disabled by default after direct news sitemap was added on 2026-03-11'
    },
    {
      enabled: false,
      source_name: 'Google News - KBS',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: 'KBS 국토부 주택공급 확대',
      notes: 'disabled by default after direct news sitemap was added on 2026-03-11'
    },
    {
      enabled: true,
      source_name: 'Google News - MBC',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: 'MBC 도심 주택공급 확대',
      notes: 'backup query for missing direct RSS'
    },
    {
      enabled: true,
      source_name: 'Google News - YTN',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: 'YTN 국토부 공급대책',
      notes: 'backup query for missing direct RSS'
    },
    {
      enabled: true,
      source_name: 'Google News - 파이낸셜뉴스',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '파이낸셜뉴스 주택공급 확대',
      notes: 'backup query for missing direct RSS'
    },
    {
      enabled: true,
      source_name: 'Google News - 데일리안',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '데일리안 1.29 공급대책',
      notes: 'backup query for missing direct RSS'
    },
    {
      enabled: true,
      source_name: 'Google News - 건설경제',
      source_type: 'google_news',
      category_group: 'backup_media',
      feed_url: '',
      keyword: '건설경제 주택공급 확대',
      notes: 'backup query for missing direct RSS'
    },
    { enabled: true, source_name: '연합뉴스', source_type: 'rss', category_group: 'wire', feed_url: 'https://www.yna.co.kr/rss/news.xml', keyword: '', notes: 'default source list' },
    { enabled: false, source_name: '뉴스1', source_type: 'rss', category_group: 'wire', feed_url: 'https://www.news1.kr/rss', keyword: '', notes: 'default disabled on 2026-03-11: URL returned HTML, not RSS' },
    { enabled: false, source_name: '뉴시스', source_type: 'rss', category_group: 'wire', feed_url: 'https://www.newsis.com/rss', keyword: '', notes: 'default disabled on 2026-03-11: URL returned HTML, not RSS' },
    { enabled: true, source_name: '뉴시스-정치', source_type: 'rss', category_group: 'wire', feed_url: 'https://newsis.com/RSS/politics.xml', keyword: '', notes: 'updated on 2026-03-11: verified working section RSS feed' },
    { enabled: true, source_name: '뉴시스-경제', source_type: 'rss', category_group: 'wire', feed_url: 'https://newsis.com/RSS/economy.xml', keyword: '', notes: 'updated on 2026-03-11: verified working section RSS feed' },
    { enabled: true, source_name: '뉴시스-사회', source_type: 'rss', category_group: 'wire', feed_url: 'https://newsis.com/RSS/society.xml', keyword: '', notes: 'updated on 2026-03-11: verified working section RSS feed' },
    { enabled: true, source_name: '조선일보', source_type: 'rss', category_group: 'national_daily', feed_url: 'https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml', keyword: '', notes: 'updated on 2026-03-11: verified working direct RSS feed' },
    { enabled: false, source_name: '중앙일보', source_type: 'rss', category_group: 'national_daily', feed_url: 'https://rss.joins.com/joins_news_list.xml', keyword: '', notes: 'default disabled on 2026-03-11: URL returned HTML service notice' },
    { enabled: true, source_name: '동아일보', source_type: 'rss', category_group: 'national_daily', feed_url: 'https://rss.donga.com/total.xml', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: '한겨레', source_type: 'rss', category_group: 'national_daily', feed_url: 'https://www.hani.co.kr/rss/', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: '경향신문', source_type: 'rss', category_group: 'national_daily', feed_url: 'https://www.khan.co.kr/rss/rssdata/total_news.xml', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: '서울신문', source_type: 'rss', category_group: 'national_daily', feed_url: 'https://www.seoul.co.kr/xml/rss/google_top.xml', keyword: '', notes: 'updated on 2026-03-11: verified working RSS feed' },
    { enabled: true, source_name: '세계일보', source_type: 'rss', category_group: 'national_daily', feed_url: 'https://www.segye.com/Articles/RSSList/segye_recent.xml', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: '매일경제', source_type: 'rss', category_group: 'economic_daily', feed_url: 'https://www.mk.co.kr/rss/30000001/', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: '한국경제', source_type: 'rss', category_group: 'economic_daily', feed_url: 'https://www.hankyung.com/feed/all-news', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: '서울경제-부동산', source_type: 'rss', category_group: 'economic_daily', feed_url: 'https://www.sedaily.com/rss/realestate', keyword: '', notes: 'updated on 2026-03-11: verified working section RSS feed' },
    { enabled: true, source_name: '서울경제-경제', source_type: 'rss', category_group: 'economic_daily', feed_url: 'https://www.sedaily.com/rss/economy', keyword: '', notes: 'updated on 2026-03-11: verified working section RSS feed' },
    { enabled: true, source_name: '서울경제-정치', source_type: 'rss', category_group: 'economic_daily', feed_url: 'https://www.sedaily.com/rss/politics', keyword: '', notes: 'updated on 2026-03-11: verified working section RSS feed' },
    { enabled: true, source_name: '이데일리', source_type: 'rss', category_group: 'economic_daily', feed_url: 'http://rss.edaily.co.kr/edaily_news.xml', keyword: '', notes: 'updated on 2026-03-11: verified working RSS feed' },
    { enabled: true, source_name: '아시아경제', source_type: 'sitemap', category_group: 'economic_daily', feed_url: 'https://www.asiae.co.kr/news/sitemap-latest-article', keyword: '', notes: 'updated on 2026-03-11: verified working news sitemap' },
    { enabled: true, source_name: '머니투데이', source_type: 'rss', category_group: 'economic_daily', feed_url: 'https://rss.mt.co.kr/mt_news.xml', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: 'KBS', source_type: 'sitemap', category_group: 'broadcast', feed_url: 'https://news.kbs.co.kr/sitemap/recentNewsList.xml', keyword: '', notes: 'updated on 2026-03-11: verified working news sitemap' },
    { enabled: false, source_name: 'MBC', source_type: 'rss', category_group: 'broadcast', feed_url: 'https://imnews.imbc.com/rss/news.xml', keyword: '', notes: 'default disabled on 2026-03-11: URL redirected to HTML error page' },
    { enabled: true, source_name: 'SBS', source_type: 'rss', category_group: 'broadcast', feed_url: 'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01', keyword: '', notes: 'default source list' },
    { enabled: false, source_name: 'YTN', source_type: 'rss', category_group: 'broadcast', feed_url: 'https://www.ytn.co.kr/_rss/news.xml', keyword: '', notes: 'default disabled on 2026-03-11: URL returned HTML/404' },
    { enabled: true, source_name: 'JTBC', source_type: 'rss', category_group: 'broadcast', feed_url: 'https://fs.jtbc.co.kr/RSS/newsflash.xml', keyword: '', notes: 'default source list' },
    { enabled: true, source_name: '노컷뉴스', source_type: 'rss', category_group: 'online_media', feed_url: 'https://rss.nocutnews.co.kr/news/news.xml', keyword: '', notes: 'updated on 2026-03-11: verified working RSS feed' },
    { enabled: true, source_name: '헤럴드경제', source_type: 'rss', category_group: 'online_media', feed_url: 'https://biz.heraldcorp.com/rss/google/newsAll', keyword: '', notes: 'updated on 2026-03-11: verified working RSS feed' },
    { enabled: false, source_name: '파이낸셜뉴스', source_type: 'rss', category_group: 'online_media', feed_url: 'https://www.fnnews.com/rss/fn_realnews.xml', keyword: '', notes: 'default disabled on 2026-03-11: URL returned HTML/404' },
    { enabled: true, source_name: '오마이뉴스', source_type: 'rss', category_group: 'online_media', feed_url: 'https://rss.ohmynews.com/rss/ohmynews.xml', keyword: '', notes: 'updated on 2026-03-11: verified working RSS feed' },
    { enabled: true, source_name: '프레시안', source_type: 'rss', category_group: 'online_media', feed_url: 'http://www.pressian.com/api/v3/site/rss/news', keyword: '', notes: 'updated on 2026-03-11: verified working RSS feed' },
    { enabled: false, source_name: '데일리안', source_type: 'rss', category_group: 'online_media', feed_url: 'https://www.dailian.co.kr/rss/all.xml', keyword: '', notes: 'default disabled on 2026-03-11: URL returned 404' },
    { enabled: true, source_name: '국토일보', source_type: 'rss', category_group: 'policy_sector', feed_url: 'http://www.ikld.kr/rss/allArticle.xml', keyword: '', notes: 'default source list' },
    { enabled: false, source_name: '건설경제', source_type: 'rss', category_group: 'policy_sector', feed_url: 'https://www.cnews.co.kr/rss/all.xml', keyword: '', notes: 'default disabled on 2026-03-11: DNS failure' }
  ],
  keywordRules: [
    { enabled: true, bucket: 'topic', keyword: '도심', weight: 2, notes: '' },
    { enabled: true, bucket: 'topic', keyword: '주택', weight: 2, notes: '' },
    { enabled: true, bucket: 'topic', keyword: '공급', weight: 2, notes: '' },
    { enabled: true, bucket: 'topic', keyword: '신속화', weight: 2, notes: '' },
    { enabled: true, bucket: 'topic', keyword: '국토부', weight: 2, notes: '' },
    { enabled: true, bucket: 'topic', keyword: '용산', weight: 3, notes: '' },
    { enabled: true, bucket: 'topic', keyword: '태릉', weight: 3, notes: '' },
    { enabled: true, bucket: 'topic', keyword: '과천', weight: 3, notes: '' },
    { enabled: true, bucket: 'phrase', keyword: '도심 주택공급 확대 및 신속화 방안', weight: 5, notes: 'always collect' },
    { enabled: true, bucket: 'phrase', keyword: '주택공급촉진 관계장관회의', weight: 5, notes: 'always collect' },
    { enabled: true, bucket: 'phrase', keyword: '1.29 공급대책', weight: 4, notes: '' },
    { enabled: true, bucket: 'phrase', keyword: '1.29 대책', weight: 4, notes: 'variant spelling' },
    { enabled: true, bucket: 'phrase', keyword: '1.29대책', weight: 4, notes: 'variant spelling' },
    { enabled: true, bucket: 'phrase', keyword: '용산 국제업무지구 공급', weight: 4, notes: '' },
    { enabled: true, bucket: 'phrase', keyword: '태릉CC 공급', weight: 4, notes: '' },
    { enabled: true, bucket: 'phrase', keyword: '과천 경마장 공급', weight: 4, notes: '' },
    { enabled: true, bucket: 'frame_policy', keyword: '발표', weight: 1, notes: '' },
    { enabled: true, bucket: 'frame_policy', keyword: '계획', weight: 1, notes: '' },
    { enabled: true, bucket: 'frame_policy', keyword: '추진', weight: 1, notes: '' },
    { enabled: true, bucket: 'frame_policy', keyword: '인허가', weight: 1, notes: '' },
    { enabled: true, bucket: 'frame_positive', keyword: '기대', weight: 1, notes: '' },
    { enabled: true, bucket: 'frame_positive', keyword: '환영', weight: 1, notes: '' },
    { enabled: true, bucket: 'frame_positive', keyword: '활성화', weight: 1, notes: '' },
    { enabled: true, bucket: 'frame_critical', keyword: '우려', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_critical', keyword: '비판', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_critical', keyword: '논란', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_critical', keyword: '반발', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_critical', keyword: '지연', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_critical', keyword: '실효성', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_political', keyword: '국회', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_political', keyword: '여당', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_political', keyword: '야당', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_political', keyword: '지자체', weight: 2, notes: '' },
    { enabled: true, bucket: 'frame_political', keyword: '부처', weight: 2, notes: '' },
    { enabled: true, bucket: 'negative_signal', keyword: '갈등', weight: 1, notes: '' },
    { enabled: true, bucket: 'negative_signal', keyword: '우려', weight: 1, notes: '' },
    { enabled: true, bucket: 'negative_signal', keyword: '비판', weight: 1, notes: '' },
    { enabled: true, bucket: 'negative_signal', keyword: '반발', weight: 1, notes: '' },
    { enabled: true, bucket: 'opinion_signal', keyword: '사설', weight: 1, notes: '' },
    { enabled: true, bucket: 'opinion_signal', keyword: '칼럼', weight: 1, notes: '' },
    { enabled: true, bucket: 'opinion_signal', keyword: '오피니언', weight: 1, notes: '' },
    { enabled: true, bucket: 'opinion_signal', keyword: '분석', weight: 1, notes: '' }
  ]
};

MM.DEFAULT_RUNTIME_SETTINGS = [
  {
    key: 'analysis_reference_time',
    value: '2026-02-01T10:00:00+09:00',
    notes: 'Default set to D+3 from 2026-01-29 10:00 KST. Blank = current execution time.'
  }
];

function ensureOperationalSheets() {
  var rawSheet = ensureSheetWithHeaders_(MM.SHEET_NAMES.RAW, MM.RAW_COLUMNS);
  ensureSheetWithHeaders_(MM.SHEET_NAMES.PROCESSED, MM.PROCESSED_COLUMNS);
  ensureSheetWithHeaders_(MM.SHEET_NAMES.BRIEFING, MM.BRIEFING_COLUMNS);
  var sourceSheet = ensureSheetWithHeaders_(MM.SHEET_NAMES.SOURCES, MM.SOURCE_COLUMNS);
  var keywordSheet = ensureSheetWithHeaders_(MM.SHEET_NAMES.KEYWORDS, MM.KEYWORD_COLUMNS);
  var runtimeSheet = ensureSheetWithHeaders_(MM.SHEET_NAMES.RUNTIME, MM.RUNTIME_COLUMNS);

  if (sourceSheet.getLastRow() <= 1) {
    appendSheetRecords_(MM.SHEET_NAMES.SOURCES, MM.SOURCE_COLUMNS, MM.DEFAULT_CONFIG.sources);
  }

  if (keywordSheet.getLastRow() <= 1) {
    appendSheetRecords_(MM.SHEET_NAMES.KEYWORDS, MM.KEYWORD_COLUMNS, MM.DEFAULT_CONFIG.keywordRules);
  }

  if (runtimeSheet.getLastRow() <= 1) {
    appendSheetRecords_(MM.SHEET_NAMES.RUNTIME, MM.RUNTIME_COLUMNS, MM.DEFAULT_RUNTIME_SETTINGS);
  }

  if (rawSheet.getFrozenRows() < 1) {
    rawSheet.setFrozenRows(1);
  }

  resetConfigCache_();
}

function getMonitoringConfig() {
  if (MM._configCache) {
    return MM._configCache;
  }

  var config = cloneObject_(MM.DEFAULT_CONFIG);
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  if (spreadsheet) {
    var sourceSheet = spreadsheet.getSheetByName(MM.SHEET_NAMES.SOURCES);
    var keywordSheet = spreadsheet.getSheetByName(MM.SHEET_NAMES.KEYWORDS);
    var runtimeSheet = spreadsheet.getSheetByName(MM.SHEET_NAMES.RUNTIME);

    if (sourceSheet && sourceSheet.getLastRow() > 1) {
      var sourceRows = readSheetRecords_(MM.SHEET_NAMES.SOURCES);
      var parsedSources = sourceRows.map(parseSourceConfigRow_).filter(function(row) {
        return row && row.source_name;
      });
      if (parsedSources.length) {
        config.sources = parsedSources;
      }
    }

    if (keywordSheet && keywordSheet.getLastRow() > 1) {
      var keywordRows = readSheetRecords_(MM.SHEET_NAMES.KEYWORDS);
      var parsedRules = keywordRows.map(parseKeywordConfigRow_).filter(function(row) {
        return row && row.keyword;
      });
      if (parsedRules.length) {
        config.keywordRules = parsedRules;
      }
    }

    if (runtimeSheet && runtimeSheet.getLastRow() > 1) {
      applyRuntimeSettings_(config, readSheetRecords_(MM.SHEET_NAMES.RUNTIME).map(parseRuntimeConfigRow_));
    }
  }

  MM._configCache = config;
  return config;
}

function resetConfigCache_() {
  MM._configCache = null;
}

function ensureSheetWithHeaders_(sheetName, headers) {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = spreadsheet.getSheetByName(sheetName);

  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }

  var expectedHeaders = headers.slice();
  var headerRange = sheet.getRange(1, 1, 1, expectedHeaders.length);
  var currentHeaders = sheet.getLastColumn() >= expectedHeaders.length ?
    sheet.getRange(1, 1, 1, expectedHeaders.length).getValues()[0] :
    [];

  if (sheet.getLastRow() === 0 || !arraysEqual_(currentHeaders, expectedHeaders)) {
    headerRange.setValues([expectedHeaders]);
  }

  if (sheet.getFrozenRows() < 1) {
    sheet.setFrozenRows(1);
  }

  return sheet;
}

function readSheetRecords_(sheetName) {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = spreadsheet.getSheetByName(sheetName);

  if (!sheet || sheet.getLastRow() <= 1) {
    return [];
  }

  var values = sheet.getRange(1, 1, sheet.getLastRow(), sheet.getLastColumn()).getValues();
  var headers = values[0];
  var bodyRows = values.slice(1);

  return bodyRows.filter(function(row) {
    return row.join('').trim() !== '';
  }).map(function(row) {
    var record = {};
    headers.forEach(function(header, index) {
      record[header] = row[index];
    });
    return record;
  });
}

function appendSheetRecords_(sheetName, columns, records) {
  if (!records || !records.length) {
    return;
  }

  var sheet = ensureSheetWithHeaders_(sheetName, columns);
  var values = records.map(function(record) {
    return columns.map(function(column) {
      return normalizeSheetValue_(record[column]);
    });
  });

  sheet.getRange(sheet.getLastRow() + 1, 1, values.length, columns.length).setValues(values);
}

function overwriteSheetRecords_(sheetName, columns, records) {
  var sheet = ensureSheetWithHeaders_(sheetName, columns);
  var lastRow = sheet.getLastRow();

  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, sheet.getMaxColumns()).clearContent();
  }

  if (records && records.length) {
    appendSheetRecords_(sheetName, columns, records);
  }
}

function parseSourceConfigRow_(row) {
  var enabled = toBoolean_(row.enabled);
  return {
    enabled: enabled,
    source_name: String(row.source_name || '').trim(),
    source_type: String(row.source_type || 'rss').trim(),
    category_group: String(row.category_group || '').trim(),
    feed_url: String(row.feed_url || '').trim(),
    keyword: String(row.keyword || '').trim(),
    notes: String(row.notes || '').trim()
  };
}

function parseKeywordConfigRow_(row) {
  return {
    enabled: toBoolean_(row.enabled),
    bucket: String(row.bucket || '').trim(),
    keyword: String(row.keyword || '').trim(),
    weight: toNumber_(row.weight, 1),
    notes: String(row.notes || '').trim()
  };
}

function parseRuntimeConfigRow_(row) {
  return {
    key: String(row.key || '').trim(),
    value: String(row.value || '').trim(),
    notes: String(row.notes || '').trim()
  };
}

function applyRuntimeSettings_(config, rows) {
  rows.forEach(function(row) {
    if (!row || !row.key) {
      return;
    }

    if (row.key === 'analysis_reference_time') {
      config.analysis.referenceTime = row.value;
    }
  });
}

function buildGoogleNewsRssUrl_(query) {
  return 'https://news.google.com/rss/search?q=' +
    encodeURIComponent(query) +
    '&hl=ko&gl=KR&ceid=KR:ko';
}

function resolveFeedUrl_(source) {
  if (source.feed_url) {
    return source.feed_url;
  }

  if (source.source_type === 'google_news' && source.keyword) {
    return buildGoogleNewsRssUrl_(source.keyword);
  }

  return '';
}

function getKeywordRulesByBuckets_(config, buckets) {
  var bucketLookup = {};
  buckets.forEach(function(bucket) {
    bucketLookup[bucket] = true;
  });

  return (config.keywordRules || []).filter(function(rule) {
    return rule.enabled !== false && bucketLookup[rule.bucket];
  });
}

function getSourcePriority_(sourceName, config) {
  var priorityMap = config.sourcePriority || {};
  var exactPriority = Number(priorityMap[sourceName] || 0);

  if (exactPriority) {
    return exactPriority;
  }

  // Support sectionized source names like "뉴시스-정치" while leaving "Google News - ..." untouched.
  if (sourceName && sourceName.indexOf(' - ') === -1 && sourceName.indexOf('-') !== -1) {
    var baseName = sourceName.split('-')[0].trim();
    return Number(priorityMap[baseName] || 0);
  }

  return 0;
}

function getLookbackStart_(config, now) {
  var current = now || new Date();
  return new Date(current.getTime() - Number(config.collection.reportLookbackHours || 36) * 60 * 60 * 1000);
}

function getAnalysisNow_(config) {
  var referenceText = collapseWhitespace_(((config || {}).analysis || {}).referenceTime);
  var parsedReference = parseDateValue_(referenceText);
  return parsedReference || new Date();
}

function getRecordTime_(record) {
  var value = record.publish_time || record.collected_time;
  return parseDateValue_(value);
}

function isRepresentativeRecord_(record) {
  return !record.duplicate_flag || record.duplicate_flag === 'representative';
}

function normalizeSheetValue_(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return value;
}

function toBoolean_(value) {
  if (value === true || value === false) {
    return value;
  }

  var text = String(value || '').trim().toLowerCase();
  return text === 'true' || text === '1' || text === 'y' || text === 'yes';
}

function toNumber_(value, fallback) {
  var numberValue = Number(value);
  return isNaN(numberValue) ? fallback : numberValue;
}

function parseDateValue_(value) {
  if (!value) {
    return null;
  }

  if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value.getTime())) {
    return value;
  }

  var parsed = new Date(value);
  return isNaN(parsed.getTime()) ? null : parsed;
}

function formatDateTime_(date, timezone) {
  var tz = timezone || getMonitoringConfig().timezone || Session.getScriptTimeZone();
  return Utilities.formatDate(date, tz, "yyyy-MM-dd'T'HH:mm:ssZ");
}

function formatReadableDateTime_(date, timezone) {
  var tz = timezone || getMonitoringConfig().timezone || Session.getScriptTimeZone();
  return Utilities.formatDate(date, tz, 'yyyy-MM-dd HH:mm');
}

function stripHtml_(html) {
  return collapseWhitespace_(String(html || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'"));
}

function collapseWhitespace_(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}

function normalizeTextLower_(text) {
  return collapseWhitespace_(String(text || '').toLowerCase());
}

function detectLanguage_(text) {
  var value = String(text || '');
  if (/[가-힣]/.test(value)) {
    return 'ko';
  }
  if (/[a-zA-Z]/.test(value)) {
    return 'en';
  }
  return 'unknown';
}

function cloneObject_(value) {
  return JSON.parse(JSON.stringify(value));
}

function arraysEqual_(left, right) {
  if (!left || !right || left.length !== right.length) {
    return false;
  }

  for (var index = 0; index < left.length; index += 1) {
    if (String(left[index] || '') !== String(right[index] || '')) {
      return false;
    }
  }

  return true;
}

function limitText_(text, maxLength) {
  var value = String(text || '');
  if (value.length <= maxLength) {
    return value;
  }
  return value.substring(0, Math.max(0, maxLength - 3)) + '...';
}

function addNote_(existingNote, fragment) {
  var current = collapseWhitespace_(existingNote);
  var addition = collapseWhitespace_(fragment);

  if (!addition) {
    return current;
  }

  if (!current) {
    return addition;
  }

  if (current.indexOf(addition) !== -1) {
    return current;
  }

  return current + ' | ' + addition;
}

function upsertTaggedNote_(existingNote, tag, value) {
  var current = collapseWhitespace_(existingNote);
  var tagPattern = new RegExp('(?:^|\\s\\|\\s)' + tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=[^|]*', 'g');
  var cleaned = collapseWhitespace_(current.replace(tagPattern, ''));
  cleaned = cleaned.replace(/\s+\|\s+\|/g, ' | ').replace(/^\|\s*/, '').replace(/\s*\|$/, '').trim();
  return addNote_(cleaned, tag + '=' + value);
}

function splitKeywords_(value) {
  return String(value || '')
    .split(/[|,]/)
    .map(function(item) {
      return collapseWhitespace_(item);
    })
    .filter(function(item) {
      return item;
    });
}

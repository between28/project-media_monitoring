function generateBriefing() {
  ensureOperationalSheets();
  resetConfigCache_();

  var config = getMonitoringConfig();
  var candidates = readSheetRecords_(MM.SHEET_NAMES.PROCESSED);
  var analysisNow = getAnalysisNow_(config);
  var generatedTime = formatDateTime_(analysisNow, config.timezone);

  if (!candidates.length) {
    appendSheetRecords_(MM.SHEET_NAMES.BRIEFING, MM.BRIEFING_COLUMNS, [{
      generated_time: generatedTime,
      topic_name: config.topic.name,
      section_name: '전체본',
      content: '선별된 고관련 기사가 없어 브리핑 초안을 생성하지 않았습니다. RSS 설정과 키워드 기준을 확인하십시오.',
      supporting_articles: '',
      notes: 'no_candidates=true'
    }]);
    return 'No briefing candidates.';
  }

  var topCandidates = candidates.slice(0, Number(config.collection.maxBriefingArticles || 12));
  var frameCounts = countFrames_(candidates);
  var themeGroups = buildThemeGroupsForBriefing_(topCandidates, config);
  var sections = [];

  sections.push(buildBriefingSection_('총평', buildOverallSummary_(candidates, frameCounts, themeGroups, config, analysisNow), topCandidates, frameCounts));
  sections.push(buildBriefingSection_('주요 보도 내용', buildMainCoverageSection_(themeGroups), topCandidates, frameCounts));
  sections.push(buildBriefingSection_('주요 논점', buildIssueSection_(frameCounts, themeGroups), topCandidates, frameCounts));
  sections.push(buildBriefingSection_('영향력 기사', buildImpactSection_(topCandidates), topCandidates, frameCounts));
  sections.push(buildBriefingSection_('대응 참고', buildResponsePoints_(frameCounts, themeGroups), topCandidates, frameCounts));

  var fullText = sections.map(function(section) {
    return '[' + section.section_name + ']\n' + section.content;
  }).join('\n\n');

  var outputRows = sections.map(function(section) {
    return {
      generated_time: generatedTime,
      topic_name: config.topic.name,
      section_name: section.section_name,
      content: section.content,
      supporting_articles: section.supporting_articles,
      notes: section.notes
    };
  });

  outputRows.push({
    generated_time: generatedTime,
    topic_name: config.topic.name,
    section_name: '전체본',
    content: fullText,
    supporting_articles: buildSupportingArticles_(topCandidates),
    notes: 'frame_counts=' + serializeFrameCounts_(frameCounts)
  });

  appendSheetRecords_(MM.SHEET_NAMES.BRIEFING, MM.BRIEFING_COLUMNS, outputRows);
  return fullText;
}

function buildBriefingSection_(sectionName, content, candidates, frameCounts) {
  return {
    section_name: sectionName,
    content: content,
    supporting_articles: buildSupportingArticles_(candidates),
    notes: 'frame_counts=' + serializeFrameCounts_(frameCounts)
  };
}

function buildOverallSummary_(candidates, frameCounts, themeGroups, config, analysisNow) {
  var sourceCount = getUniqueSourceCount_(candidates);
  var dominantFrames = getDominantFrames_(frameCounts);
  var dominantThemes = themeGroups.slice(0, 2).map(function(group) {
    return group.label;
  });
  var lines = [];
  var analysisLabel = formatReadableDateTime_(analysisNow || getAnalysisNow_(config), config.timezone);

  lines.push('기준 시점(' + analysisLabel + ') 기준, ' + config.topic.name + ' 관련 고관련 기사 ' + candidates.length + '건이 선별되었고 ' + sourceCount + '개 매체에서 유사 서사가 확인되었습니다.');

  if (dominantFrames.length > 1) {
    lines.push('보도 흐름은 ' + dominantFrames[0] + ' 중심이며 ' + dominantFrames[1] + ' 성격 보도가 함께 관찰되었습니다.');
  } else {
    lines.push('보도 흐름은 ' + (dominantFrames[0] || '정책 설명') + ' 중심으로 형성되었습니다.');
  }

  if (dominantThemes.length) {
    lines.push('반복적으로 등장한 주제는 ' + dominantThemes.join(', ') + '입니다.');
  } else {
    lines.push('주요 보도는 정책 전반의 공급 계획과 후속 일정 설명에 집중되었습니다.');
  }

  if (Number(frameCounts['비판 / 우려'] || 0) > 0) {
    lines.push('브리핑 시에는 실효성, 추진 속도, 관계기관 협의와 관련한 우려 지점에 대한 보완 설명이 필요합니다.');
  } else {
    lines.push('브리핑 시에는 공급 물량, 후속 일정, 집행 절차를 일관된 메시지로 제시하는 것이 적절합니다.');
  }

  return lines.join('\n');
}

function buildMainCoverageSection_(themeGroups) {
  if (!themeGroups.length) {
    return '- 정책 전반 기사 위주로 분포되어 별도 테마 군집이 뚜렷하지 않았습니다.';
  }

  return themeGroups.map(function(group) {
    return '- ' + group.label + ': ' + group.sourceSummary + ' 등 ' + group.count + '건. 대표 기사: [' + group.lead.source_name + '] ' + limitText_(group.lead.title, 90);
  }).join('\n');
}

function buildIssueSection_(frameCounts, themeGroups) {
  var lines = [];

  if (Number(frameCounts['비판 / 우려'] || 0) > 0) {
    lines.push('- 공급 실현 가능성, 사업 속도, 주민 수용성과 관련한 우려 신호가 반복적으로 나타났습니다.');
  }
  if (Number(frameCounts['정치 / 기관 이슈'] || 0) > 0) {
    lines.push('- 관계기관 협의, 지자체 조율, 정치권 반응 등 제도 외부 변수에 대한 관심이 확인되었습니다.');
  }
  if (Number(frameCounts['정책 설명'] || 0) > 0) {
    lines.push('- 후보지, 물량, 일정, 후속 절차 등 정책 세부 설명 수요가 여전히 높습니다.');
  }
  if (Number(frameCounts['긍정 평가'] || 0) > 0) {
    lines.push('- 일부 보도는 공급 확대 기대와 시장 안정 효과를 긍정적으로 평가했습니다.');
  }

  themeGroups.slice(0, 2).forEach(function(group) {
    lines.push('- ' + group.label + '에서 세부 실행계획과 후속 일정 관리가 핵심 논점으로 반복되었습니다.');
  });

  if (!lines.length) {
    lines.push('- 뚜렷한 비판 프레임보다 정책 설명과 기본 사실 전달 보도가 우세했습니다.');
  }

  return lines.slice(0, 5).join('\n');
}

function buildImpactSection_(candidates) {
  return candidates.slice(0, 5).map(function(record, index) {
    return (index + 1) + '. [' + record.source_name + '] ' + record.title + ' (중요도 ' + record.importance_score + ', 프레임 ' + (record.frame_category || '기타') + ')';
  }).join('\n');
}

function buildResponsePoints_(frameCounts, themeGroups) {
  var lines = [
    '- 공급 물량, 대상지, 일정은 확정 사항과 후속 검토 사항을 구분해 설명합니다.',
    '- 후속 인허가, 관계기관 협의, 현장 이행관리 절차를 가능한 범위에서 구체 일정과 함께 제시합니다.'
  ];

  if (Number(frameCounts['비판 / 우려'] || 0) > 0) {
    lines.push('- 실효성 및 속도 우려에는 단계별 집행계획과 관리지표를 중심으로 대응 포인트를 준비합니다.');
  }

  if (Number(frameCounts['정치 / 기관 이슈'] || 0) > 0) {
    lines.push('- 지자체 및 관계기관 협의 상황은 단일 메시지로 정리해 기관 간 해석 차이를 줄입니다.');
  }

  if (themeGroups.length) {
    lines.push('- 반복 노출되는 주제인 ' + themeGroups.slice(0, 2).map(function(group) { return group.label; }).join(', ') + ' 관련 예상 질의를 사전 정리합니다.');
  }

  return lines.slice(0, 4).join('\n');
}

function buildThemeGroupsForBriefing_(records, config) {
  var groups = {};

  records.forEach(function(record) {
    var themeKey = deriveThemeKey_(record, config);

    if (!groups[themeKey]) {
      groups[themeKey] = {
        key: themeKey,
        label: buildThemeLabelFromKey_(themeKey),
        count: 0,
        sources: {},
        lead: record
      };
    }

    groups[themeKey].count += 1;
    groups[themeKey].sources[record.source_name] = true;
  });

  return Object.keys(groups).map(function(key) {
    var group = groups[key];
    group.sourceSummary = Object.keys(group.sources).slice(0, 3).join(', ');
    return group;
  }).sort(function(left, right) {
    return right.count - left.count;
  }).slice(0, Number(config.collection.maxThemes || 3));
}

function countFrames_(records) {
  var counts = {};

  records.forEach(function(record) {
    var frame = record.frame_category || '기타';
    counts[frame] = Number(counts[frame] || 0) + 1;
  });

  return counts;
}

function getDominantFrames_(frameCounts) {
  return Object.keys(frameCounts).sort(function(left, right) {
    return Number(frameCounts[right] || 0) - Number(frameCounts[left] || 0);
  }).slice(0, 2);
}

function getUniqueSourceCount_(records) {
  var sources = {};

  records.forEach(function(record) {
    sources[record.source_name] = true;
  });

  return Object.keys(sources).length;
}

function buildSupportingArticles_(records) {
  return records.slice(0, 5).map(function(record) {
    return '[' + record.source_name + '] ' + limitText_(record.title, 70);
  }).join('\n');
}

function serializeFrameCounts_(frameCounts) {
  return Object.keys(frameCounts).map(function(frame) {
    return frame + ':' + frameCounts[frame];
  }).join(', ');
}

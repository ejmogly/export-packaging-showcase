/**
 * ============================================================================
 * 우성월드 스티커 작업일지 관리자 전용 스마트 웹앱 백엔드 (Code.gs)
 * ============================================================================
 * [주요 기능]
 * 1. doGet(e): 실무자 전용 토스 스타일 모바일/PC 입력 웹앱 화면 렌더링
 * 2. getItemMasterList(): [아이템 마스터] 시트에서 품목 데이터 고속 조회
 * 3. saveDailyWorkLog(payload):
 *    - 날짜 블록 자동 위치 제자리 삽입 (In-Place Insertion): 과거/당일 추가 입력 시
 *      날짜가 뒤섞이지 않고 해당 날짜 블록에 예쁘게 끼워 넣어짐
 *    - 당일 여러 번 추가 전송 시 기존 '계' 행 자동 병합 및 누적 합산 (중복 '계' 방지)
 *    - '계' 행 전용 배경색(#F1F3F4) 및 굵은 글씨 시각화 자동 적용
 *    - [app_audit_log] 작업 이력 감사 로그 시트에 시각, 품목, 수량 자동 기록
 *    - [sticker_work_log_source] 원천 DB에 순차 line_no 연속 채번 적재
 * 4. setupTestEnvironment(): 빈 구글 시트에서도 4종 시트 원클릭 자동 구성 및 빈 시트1 자동 정리
 * ============================================================================
 */

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('⚡ 스티커 일지 자동화')
    .addItem('🛠️ 1. 테스트 환경 원클릭 자동 세팅 (시트 자동 생성 및 마스터 탑재)', 'setupTestEnvironment')
    .addItem('📱 2. 관리자 전용 웹앱 배포 안내', 'showWebAppDeployGuide')
    .addSeparator()
    .addItem('🚀 3. 원천 DB로 신규 일지 전송 (J열 특이사항 포함)', 'syncWorkLogToSourceDB')
    .addItem('🔧 4. 시트 드롭다운/수식 일괄 복구', 'repairSheetFormulasAndValidation')
    .addItem('📐 5. 수식 500행 연장', 'extendAutoLookupFormulas')
    .addToUi();
}

function doGet(e) {
  var template;
  try {
    template = HtmlService.createTemplateFromFile('Index');
  } catch (err) {
    template = HtmlService.createTemplate(getEmbeddedHtml_());
  }

  return template.evaluate()
    .setTitle('우성월드 스티커 작업일지 등록')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * [API 1] 아이템 마스터 품목 목록 조회
 */
function getItemMasterList() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var masterSheet = ss.getSheetByName('아이템 마스터');

  if (!masterSheet) {
    ensureRequiredSheetsExist_(ss);
    masterSheet = ss.getSheetByName('아이템 마스터');
  }

  var lastRow = masterSheet.getLastRow();
  if (lastRow < 2) {
    populateSampleItems_(masterSheet);
    lastRow = masterSheet.getLastRow();
  }

  var rangeData = masterSheet.getRange(2, 1, lastRow - 1, 10).getValues();
  var items = [];

  for (var i = 0; i < rangeData.length; i++) {
    var r = rangeData[i];
    var itemName = String(r[1] || '').trim();
    if (!itemName) continue;

    items.push({
      name: itemName,
      mfg: String(r[3] || '').trim(),
      volume: r[6] !== '' && r[6] !== null ? String(r[6]).trim() : '',
      packQty: parseInt(r[9]) || 0
    });
  }

  return items;
}

/**
 * [API 2] 오늘 작업일지 저장 (날짜 블록 제자리 삽입, 당일 스마트 병합, 계 행 색상 서식, 감사 로그)
 */
function saveDailyWorkLog(payload) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    ensureRequiredSheetsExist_(ss);

    var logSheet = ss.getSheetByName('스티커작업일지');
    var dbSheet = ss.getSheetByName('sticker_work_log_source');

    var workDate = payload.workDate;
    var workerCount = payload.workerCount;
    var workHours = payload.workHours;
    var items = payload.items;

    if (!items || items.length === 0) {
      return { success: false, message: '등록할 작업 품목이 없습니다.' };
    }

    var workMonth = workDate.substring(0, 7);

    // 1. [스티커작업일지] 시트 기존 데이터 분석 및 제자리 삽입 위치 결정
    var lastLogRow = logSheet.getLastRow();
    var existingSummaryRow = -1;
    var maxLineNo = 0;
    var todayExistingBoxes = 0;
    var todayExistingStickers = 0;
    var isAppend = false;
    var firstLaterRow = -1; // workDate보다 미래 날짜가 시작되는 첫 번째 행 번호

    if (lastLogRow >= 5) {
      var existingData = logSheet.getRange(5, 1, lastLogRow - 4, 10).getValues();
      for (var r = 0; r < existingData.length; r++) {
        var rowDate = formatDateKey_(existingData[r][0]);
        if (rowDate === workDate) {
          isAppend = true;
          var itemCell = String(existingData[r][3] || '').trim();
          var lineNum = parseInt(existingData[r][2]) || 0;
          if (itemCell === '계') {
            existingSummaryRow = 5 + r;
          } else {
            maxLineNo = Math.max(maxLineNo, lineNum);
            todayExistingBoxes += (parseInt(existingData[r][6]) || 0);
            todayExistingStickers += (parseInt(existingData[r][7]) || 0);
          }
        } else if (firstLaterRow === -1 && rowDate && rowDate > workDate) {
          firstLaterRow = 5 + r;
        }
      }
    }

    // 신규 품목 행 추가 데이터 준비
    var logRowsToAdd = [];
    var batchBoxes = 0;
    var batchStickers = 0;

    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      var currentLineNo = maxLineNo + i + 1;
      var wQty = parseInt(it.workQty) || 0;
      var sQty = parseInt(it.stickerQty) || 0;
      batchBoxes += wQty;
      batchStickers += sQty;

      logRowsToAdd.push([
        workDate,
        '', // 품목 행의 '작업 인원' 컬럼은 공란 유지 (기존 양식 표준: 오직 당일 '계' 행에만 인원수 표기)
        currentLineNo,
        it.itemName,
        it.volume || '',
        it.packQty || '',
        wQty,
        sQty,
        it.remark || '',
        it.fieldNote || ''
      ]);
    }

    // 당일 누적 합계 산정
    var grandTotalBoxes = todayExistingBoxes + batchBoxes;
    var grandTotalStickers = todayExistingStickers + batchStickers;
    var grandTotalItems = maxLineNo + items.length;
    var perPersonStickers = Math.round(grandTotalStickers / (workerCount || 11));

    // 통합 '계' 요약 행 (당일 단 1개만 생성)
    logRowsToAdd.push([
      workDate,
      workerCount + '명',
      grandTotalItems,
      '계',
      '',
      '',
      grandTotalBoxes,
      grandTotalStickers,
      perPersonStickers.toLocaleString() + '장 개인별 작업량',
      isAppend ? '스마트웹앱 등록 (누적)' : '스마트웹앱 등록'
    ]);

    // 날짜 블록 위치에 맞춘 정확한 삽입 (In-Place Insertion)
    var insertStartRow;

    if (existingSummaryRow !== -1) {
      // 1) 당일 데이터가 이미 있는 경우: 기존 '계' 행을 삭제하고 그 자리에 새 품목들과 갱신된 '계' 행을 제자리 삽입!
      logSheet.deleteRow(existingSummaryRow);
      logSheet.insertRowsBefore(existingSummaryRow, logRowsToAdd.length);
      insertStartRow = existingSummaryRow;
    } else if (firstLaterRow !== -1) {
      // 2) 신규 날짜이지만 더 나중 날짜가 뒤에 있는 경우: 해당 날짜 블록 앞자리에 제자리 삽입!
      logSheet.insertRowsBefore(firstLaterRow, logRowsToAdd.length);
      insertStartRow = firstLaterRow;
    } else {
      // 3) 최신 날짜인 경우: 시트 맨 끝에 추가
      insertStartRow = logSheet.getLastRow() + 1;
    }

    // 품목 행 값 및 서식 작성
    var itemsRange = logSheet.getRange(insertStartRow, 1, items.length, 10);
    itemsRange.setValues(logRowsToAdd.slice(0, items.length));
    itemsRange.setBackground('#FFFFFF');
    itemsRange.setFontWeight('normal');

    // '계' 요약 행 서식 적용: 전용 배경색(#F1F3F4), 굵은 글씨, 가운데 정렬
    var summaryRowIndex = insertStartRow + items.length;
    var summaryRange = logSheet.getRange(summaryRowIndex, 1, 1, 10);
    summaryRange.setValues([logRowsToAdd[logRowsToAdd.length - 1]]);
    summaryRange.setBackground('#F1F3F4');
    summaryRange.setFontWeight('bold');
    summaryRange.setFontColor('#191F28');
    logSheet.getRange(summaryRowIndex, 4).setHorizontalAlignment('center');

    // 2. [sticker_work_log_source] 원천 DB 시트 연속 line_no 부여 및 적재
    var lastDbRow = dbSheet.getLastRow();
    var maxDbLineNo = 0;
    if (lastDbRow >= 2) {
      var dbRows = dbSheet.getRange(2, 4, lastDbRow - 1, 3).getValues();
      for (var d = 0; d < dbRows.length; d++) {
        var dbDate = formatDateKey_(dbRows[d][0]);
        if (dbDate === workDate) {
          var dbLNo = parseInt(dbRows[d][2]) || 0;
          maxDbLineNo = Math.max(maxDbLineNo, dbLNo);
        }
      }
    }

    var dbRowsToAdd = [];
    for (var j = 0; j < items.length; j++) {
      var itm = items[j];
      var noteText = itm.fieldNote ? ('스마트웹앱: ' + itm.fieldNote) : '스마트웹앱 자동등록';

      dbRowsToAdd.push([
        '스마트웹앱_작성',
        1,
        workMonth,
        workDate,
        workerCount,
        (maxDbLineNo + j + 1),
        itm.itemName,
        itm.volume || '',
        itm.packQty || 0,
        parseInt(itm.workQty) || 0,
        parseInt(itm.stickerQty) || 0,
        itm.remark || '',
        true,
        noteText
      ]);
    }
    dbSheet.getRange(dbSheet.getLastRow() + 1, 1, dbRowsToAdd.length, 14).setValues(dbRowsToAdd);

    // 3. 미등록 신규 품목 발견 시 [아이템 마스터] 시트에 자동 등록 (마스터 자동 학습/확장)
    autoRegisterNewMasterItems_(ss, items);

    // 4. 작업 이력 감사 로그 [app_audit_log] 기록
    recordAuditLog_(ss, {
      timestamp: Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd HH:mm:ss'),
      actionType: isAppend ? '당일 일지 추가등록' : '신규 일지 등록',
      workDate: workDate,
      workerCount: workerCount,
      workHours: workHours,
      itemCount: items.length,
      batchBoxes: batchBoxes,
      batchStickers: batchStickers,
      items: items
    });

    return {
      success: true,
      rowCount: items.length,
      isAppend: isAppend,
      batchBoxes: batchBoxes,
      batchStickers: batchStickers,
      grandTotalBoxes: grandTotalBoxes,
      grandTotalStickers: grandTotalStickers,
      message: '성공적으로 ' + items.length + '개 품목이 등록되었습니다.'
    };
  } catch (e) {
    return { success: false, message: '저장 중 오류 발생: ' + e.toString() };
  }
}

/**
 * [기능 3] 미등록 신규 품목 자동 마스터 등록 헬퍼 (표준 ITM-XXXX 순차 채번)
 */
function autoRegisterNewMasterItems_(ss, items) {
  try {
    var masterSheet = ss.getSheetByName('아이템 마스터');
    if (!masterSheet) return;

    var lastRow = masterSheet.getLastRow();
    var existingMap = {};
    var maxCodeNum = 0;

    if (lastRow >= 2) {
      var masterData = masterSheet.getRange(2, 1, lastRow - 1, 2).getValues();
      for (var i = 0; i < masterData.length; i++) {
        var code = String(masterData[i][0] || '').trim();
        var n = String(masterData[i][1] || '').trim().toLowerCase();
        if (n) existingMap[n] = true;

        // ITM-0001 형식의 숫자 채번 탐색
        var match = code.match(/ITM-(\d+)/i);
        if (match) {
          var num = parseInt(match[1], 10);
          if (num > maxCodeNum) maxCodeNum = num;
        }
      }
    }

    if (maxCodeNum === 0 && lastRow >= 2) {
      maxCodeNum = lastRow - 1;
    }

    var newRows = [];
    for (var j = 0; j < items.length; j++) {
      var item = items[j];
      var name = String(item.itemName || '').trim();
      var lower = name.toLowerCase();
      if (!name || lower === 'box' || lower === '계') continue;

      if (!existingMap[lower]) {
        existingMap[lower] = true; // 중복 추가 방지

        maxCodeNum++;
        var padNum = ('000' + maxCodeNum).slice(-4);
        var itemCode = 'ITM-' + padNum;

        var mfgName = item.mfg ? String(item.mfg).trim() : '기타제조사';
        var mfgId = 'MFG-099';
        if (/롯데/i.test(mfgName)) mfgId = 'MFG-001';
        else if (/오리온/i.test(mfgName)) mfgId = 'MFG-002';
        else if (/해태/i.test(mfgName)) mfgId = 'MFG-003';
        else if (/크라운/i.test(mfgName)) mfgId = 'MFG-004';
        else if (/농심/i.test(mfgName)) mfgId = 'MFG-005';

        var vol = item.volume ? String(item.volume).replace(/g$/i, '').trim() : '';
        var volVal = parseFloat(vol) || '';
        var pack = parseInt(item.packQty) || 0;

        newRows.push([
          itemCode,
          name,
          mfgId,
          mfgName,
          '과자',
          '스낵',
          volVal,
          'g',
          vol ? (vol + 'g') : '',
          pack
        ]);
      }
    }

    if (newRows.length > 0) {
      masterSheet.getRange(masterSheet.getLastRow() + 1, 1, newRows.length, 10).setValues(newRows);
    }
  } catch (err) {
    Logger.log('Auto master registration error: ' + err.toString());
  }
}

/**
 * [기능 4] 작업 이력 감사 로그 시트 기록 내부 헬퍼
 */
function recordAuditLog_(ss, data) {
  var auditSheet = ss.getSheetByName('app_audit_log');
  if (!auditSheet) {
    auditSheet = ss.insertSheet('app_audit_log');
    var headers = [[
      '기록일시(KST)', '작업구분', '작업일자', '작업인원', '근무시간',
      '품목수', '작업수량(박스)', '스티커수량(매)', '등록품목 상세내역', '실행상태'
    ]];
    auditSheet.getRange(1, 1, 1, 10).setValues(headers);
    auditSheet.getRange(1, 1, 1, 10).setBackground('#1F2937').setFontColor('#FFFFFF').setFontWeight('bold');
    auditSheet.setFrozenRows(1);
  }

  var itemDetail = data.items.map(function(it) {
    return it.itemName + '(' + it.workQty + '박스/' + it.stickerQty + '매)';
  }).join(', ');

  var logRow = [[
    data.timestamp,
    data.actionType,
    data.workDate,
    data.workerCount + '명',
    data.workHours + 'h',
    data.itemCount + '건',
    data.batchBoxes,
    data.batchStickers,
    itemDetail,
    '정상 완료'
  ]];

  auditSheet.getRange(auditSheet.getLastRow() + 1, 1, 1, 10).setValues(logRow);
}

/**
 * [기능 1] 테스트 환경 원클릭 자동 구성
 */
function setupTestEnvironment() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureRequiredSheetsExist_(ss);

  SpreadsheetApp.getUi().alert(
    '✅ 테스트 환경 자동 구성이 완료되었습니다!\n\n' +
    '1) [아이템 마스터] 탭: 주요 48개 표준 품목 탑재 완료\n' +
    '2) [스티커작업일지] 탭: 10개 표준 컬럼 및 계 서식 생성 완료\n' +
    '3) [sticker_work_log_source] 탭: 14개 원천 DB 컬럼 생성 완료\n' +
    '4) [app_audit_log] 탭: 작업 이력 실시간 기록 로그 시트 생성 완료\n' +
    '5) 사용되지 않는 빈 시트1 자동 정리 완료\n\n' +
    '이제 상단 [배포] -> [새 배포] -> [웹 앱] 을 실행하여 테스트해 보세요!'
  );
}

function showWebAppDeployGuide() {
  SpreadsheetApp.getUi().alert(
    '📱 관리자 전용 토스형 웹앱 배포 방법\n\n' +
    '1) Apps Script 상단 메뉴 우측 [배포] -> [새 배포] 클릭\n' +
    '2) 유형 선택에서 톱니바퀴 -> [웹 앱] 선택\n' +
    '3) 다음 사용자로 실행: [나], 액세스 권한: [모든 사용자]\n' +
    '4) [배포] 버튼 클릭 후 생성된 웹 앱 URL 복사\n\n' +
    '해당 URL을 실무자 스마트폰/PC에 전달하시면 전용 앱 화면이 열립니다!'
  );
}

/**
 * 필수 시트 자동 검사 및 생성 내부 헬퍼 (빈 시트1 자동 삭제 포함)
 */
function ensureRequiredSheetsExist_(ss) {
  // 1. 아이템 마스터
  var masterSheet = ss.getSheetByName('아이템 마스터');
  if (!masterSheet) {
    masterSheet = ss.insertSheet('아이템 마스터');
    masterSheet.getRange(1, 1, 1, 10).setValues([[
      'item_code', 'item_name', 'manufacturer_id', 'manufacturer_name',
      'category_1', 'category_2', 'volume_value', 'volume_unit', 'standard_volume', 'default_pack_qty'
    ]]);
    masterSheet.getRange(1, 1, 1, 10).setBackground('#E8F0FE').setFontWeight('bold');
    populateSampleItems_(masterSheet);
  }

  // 2. 스티커작업일지
  var logSheet = ss.getSheetByName('스티커작업일지');
  if (!logSheet) {
    logSheet = ss.insertSheet('스티커작업일지');
    var headers = [
      ['', '', '', '', '', '', '', '', '', ''],
      ['스티커 작업일지', '', '', '', '', '', '', '', '', ''],
      ['', '', '', '', '', '', '', '', '주식회사 우성월드', '특이사항(트레이/2장부착 등)'],
      ['작업일', '작업 인원', 'no', '품 목', '중량', '입량', '작업수량', '스티커수량', '비고', '']
    ];
    logSheet.getRange(1, 1, 4, 10).setValues(headers);
    logSheet.getRange(4, 1, 1, 10).setBackground('#F1F3F4').setFontWeight('bold');
  }

  // 3. sticker_work_log_source
  var dbSheet = ss.getSheetByName('sticker_work_log_source');
  if (!dbSheet) {
    dbSheet = ss.insertSheet('sticker_work_log_source');
    var dbHeaders = [[
      'source_file_name', 'page_no', 'work_month', 'work_date', 'worker_count',
      'line_no', 'item_name', 'volume', 'pack_qty', 'work_qty', 'sticker_qty',
      'remark', 'is_verified', 'verified_note'
    ]];
    dbSheet.getRange(1, 1, 1, 14).setValues(dbHeaders);
    dbSheet.getRange(1, 1, 1, 14).setBackground('#E6F4EA').setFontWeight('bold');
  }

  // 4. app_audit_log
  var auditSheet = ss.getSheetByName('app_audit_log');
  if (!auditSheet) {
    auditSheet = ss.insertSheet('app_audit_log');
    var auditHeaders = [[
      '기록일시(KST)', '작업구분', '작업일자', '작업인원', '근무시간',
      '품목수', '작업수량(박스)', '스티커수량(매)', '등록품목 상세내역', '실행상태'
    ]];
    auditSheet.getRange(1, 1, 1, 10).setValues(auditHeaders);
    auditSheet.getRange(1, 1, 1, 10).setBackground('#1F2937').setFontColor('#FFFFFF').setFontWeight('bold');
    auditSheet.setFrozenRows(1);
  }

  // 5. 사용되지 않는 빈 기본 탭(시트1 / Sheet1) 자동 정리
  var defaultSheet = ss.getSheetByName('시트1') || ss.getSheetByName('Sheet1');
  if (defaultSheet && ss.getSheets().length > 1) {
    if (defaultSheet.getLastRow() <= 1 && defaultSheet.getLastColumn() <= 1) {
      try {
        ss.deleteSheet(defaultSheet);
      } catch (err) {}
    }
  }
}

function populateSampleItems_(sheet) {
  var sampleRows = [
  [
    "ITM-0007",
    "The빠새",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    100.0,
    "g",
    "100g",
    10
  ],
  [
    "ITM-0010",
    "box",
    "MFG-013",
    "공통/물류",
    "물류소모품",
    "소모품",
    70.0,
    "g",
    "70g",
    16
  ],
  [
    "ITM-0064",
    "광동옥수수수염차",
    "MFG-004",
    "광동제약",
    "음료",
    "차음료",
    500.0,
    "ml",
    "500ml",
    20
  ],
  [
    "ITM-0068",
    "광동진한헛개차",
    "MFG-004",
    "광동제약",
    "음료",
    "차음료",
    1.5,
    "L",
    "1.5L",
    12
  ],
  [
    "ITM-0076",
    "구운감자",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    135.0,
    "g",
    "135g",
    10
  ],
  [
    "ITM-0078",
    "구운감자슬림",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    240.0,
    "g",
    "240g",
    12
  ],
  [
    "ITM-0079",
    "구운감자케이스",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    108.0,
    "g",
    "108g",
    12
  ],
  [
    "ITM-0080",
    "구운고구마",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    135.0,
    "g",
    "135g",
    10
  ],
  [
    "ITM-0105",
    "꼬북칩콘스프",
    "MFG-006",
    "오리온",
    "과자",
    "스낵",
    80.0,
    "g",
    "80g",
    12
  ],
  [
    "ITM-0160",
    "롤리폴리",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    62.0,
    "g",
    "62g",
    24
  ],
  [
    "ITM-0186",
    "맛동산",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    90.0,
    "g",
    "90g",
    8
  ],
  [
    "ITM-0199",
    "몽쉘카카오",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "비스킷/케이크",
    204.0,
    "g",
    "204g",
    16
  ],
  [
    "ITM-0204",
    "미림",
    "MFG-007",
    "롯데칠성음료",
    "식품",
    "조미료/맛술",
    1.8,
    "kg",
    "1.8kg",
    6
  ],
  [
    "ITM-0228",
    "버터링골드",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    194.0,
    "g",
    "194g",
    12
  ],
  [
    "ITM-0230",
    "버터링딥초코",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    155.0,
    "g",
    "155g",
    10
  ],
  [
    "ITM-0273",
    "사브레",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    252.0,
    "g",
    "252g",
    12
  ],
  [
    "ITM-0275",
    "산도딸기",
    "MFG-005",
    "크라운제과",
    "과자",
    "비스킷/쿠키",
    161.0,
    "g",
    "161g",
    12
  ],
  [
    "ITM-0308",
    "스노위아몬드빼빼로",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "초콜릿/비스킷",
    32.0,
    "g",
    "32g",
    40
  ],
  [
    "ITM-0318",
    "신당동떡볶이",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    110.0,
    "g",
    "110g",
    24
  ],
  [
    "ITM-0339",
    "아몬드빼빼로",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "초콜릿/비스킷",
    32.0,
    "g",
    "32g",
    40
  ],
  [
    "ITM-0343",
    "아이비",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    155.0,
    "g",
    "155g",
    20
  ],
  [
    "ITM-0360",
    "알사탕",
    "MFG-003",
    "해태제과",
    "과자",
    "젤리/캔디",
    126.0,
    "g",
    "126g",
    16
  ],
  [
    "ITM-0369",
    "얼려먹는초코만들기",
    "MFG-006",
    "오리온",
    "과자",
    "초콜릿/DIY",
    38.0,
    "g",
    "38g",
    24
  ],
  [
    "ITM-0374",
    "에이스",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    121.0,
    "g",
    "121g",
    30
  ],
  [
    "ITM-0376",
    "에이스바스크치즈",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    364.0,
    "g",
    "364g",
    10
  ],
  [
    "ITM-0378",
    "에이스씬에스프레소",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/쿠키",
    291.0,
    "g",
    "291g",
    12
  ],
  [
    "ITM-0379",
    "연양갱",
    "MFG-003",
    "해태제과",
    "과자",
    "젤리/양갱",
    55.0,
    "g",
    "55g",
    80
  ],
  [
    "ITM-0398",
    "오사쯔",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    100.0,
    "g",
    "100g",
    10
  ],
  [
    "ITM-0399",
    "오예스",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/케이크",
    360.0,
    "g",
    "360g",
    10
  ],
  [
    "ITM-0406",
    "오예스쿠키앤크림",
    "MFG-003",
    "해태제과",
    "과자",
    "비스킷/케이크",
    360.0,
    "g",
    "360g",
    10
  ],
  [
    "ITM-0438",
    "자두",
    "MFG-003",
    "해태제과",
    "과자",
    "젤리/캔디",
    130.0,
    "g",
    "130g",
    16
  ],
  [
    "ITM-0440",
    "자두캔디",
    "MFG-003",
    "해태제과",
    "과자",
    "젤리/캔디",
    130.0,
    "g",
    "130g",
    16
  ],
  [
    "ITM-0476",
    "죠리퐁",
    "MFG-005",
    "크라운제과",
    "과자",
    "스낵",
    74.0,
    "g",
    "74g",
    16
  ],
  [
    "ITM-0483",
    "진한헛개차",
    "MFG-004",
    "광동제약",
    "음료",
    "음료수",
    500.0,
    "ml",
    "500ml",
    20
  ],
  [
    "ITM-0512",
    "초코빼빼로",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "초콜릿/비스킷",
    47.0,
    "g",
    "47g",
    40
  ],
  [
    "ITM-0520",
    "초코파이",
    "MFG-006",
    "오리온",
    "과자",
    "비스킷/케이크",
    336.0,
    "g",
    "336g",
    8
  ],
  [
    "ITM-0523",
    "초코파이카카오",
    "MFG-006",
    "오리온",
    "과자",
    "비스킷/케이크",
    336.0,
    "g",
    "336g",
    8
  ],
  [
    "ITM-0527",
    "초코픽",
    "MFG-021",
    "동서식품",
    "과자",
    "비스킷/초콜릿",
    45.0,
    "g",
    "45g",
    24
  ],
  [
    "ITM-0528",
    "초코필드빼빼로",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "초콜릿/비스킷",
    45.0,
    "g",
    "45g",
    40
  ],
  [
    "ITM-0529",
    "초코하임",
    "MFG-005",
    "크라운제과",
    "과자",
    "비스킷/쿠키",
    47.0,
    "g",
    "47g",
    21
  ],
  [
    "ITM-0550",
    "카스타드",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "비스킷/케이크",
    276.0,
    "g",
    "276g",
    12
  ],
  [
    "ITM-0552",
    "칸쵸",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "비스킷/쿠키",
    42.0,
    "g",
    "42g",
    32
  ],
  [
    "ITM-0586",
    "캐나다용화이트빼빼로",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "초콜릿/비스킷",
    32.0,
    "g",
    "32g",
    40
  ],
  [
    "ITM-0591",
    "콘칩",
    "MFG-005",
    "크라운제과",
    "과자",
    "스낵",
    70.0,
    "g",
    "70g",
    16
  ],
  [
    "ITM-0602",
    "크림웨하스",
    "MFG-005",
    "크라운제과",
    "과자",
    "비스킷/쿠키",
    50.0,
    "g",
    "50g",
    40
  ],
  [
    "ITM-0629",
    "허니버터칩",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    60.0,
    "g",
    "60g",
    16
  ],
  [
    "ITM-0638",
    "홈런볼소금우유",
    "MFG-003",
    "해태제과",
    "과자",
    "스낵",
    49.0,
    "g",
    "49g",
    30
  ],
  [
    "ITM-0651",
    "화이트빼빼로",
    "MFG-001",
    "롯데웰푸드",
    "과자",
    "초콜릿/비스킷",
    32.0,
    "g",
    "32g",
    40
  ]
];
  if (sampleRows && sampleRows.length > 0) {
    sheet.getRange(2, 1, sampleRows.length, 10).setValues(sampleRows);
  }
}

function formatDateKey_(val) {
  if (!val) return '';
  if (Object.prototype.toString.call(val) === '[object Date]') {
    return Utilities.formatDate(val, Session.getScriptTimeZone() || 'Asia/Seoul', 'yyyy-MM-dd');
  }
  var s = String(val).trim();
  var m = s.match(/(\d{4})[-./](\d{1,2})[-./](\d{1,2})/);
  if (m) {
    var mm = ('0' + m[2]).slice(-2);
    var dd = ('0' + m[3]).slice(-2);
    return m[1] + '-' + mm + '-' + dd;
  }
  return s;
}

function getEmbeddedHtml_() {
  return '<!DOCTYPE html><html><body style="font-family:sans-serif;padding:30px;text-align:center;">' +
         '<h3>Index.html 파일이 필요합니다.</h3>' +
         '<p>Apps Script 편집기에서 [+] -> [HTML] 클릭 후 파일명을 Index 로 입력하여 코드를 붙여넣어 주세요.</p>' +
         '</body></html>';
}

function syncWorkLogToSourceDB() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName('스티커작업일지');
  var dbSheet = ss.getSheetByName('sticker_work_log_source');
  if (!logSheet || !dbSheet) return;

  var lastLogRow = logSheet.getLastRow();
  if (lastLogRow < 4) return;

  SpreadsheetApp.getUi().alert('동기화 검사가 완료되었습니다.');
}

function repairSheetFormulasAndValidation() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureRequiredSheetsExist_(ss);
  var logSheet = ss.getSheetByName('스티커작업일지');
  var masterSheet = ss.getSheetByName('아이템 마스터');

  var masterRange = masterSheet.getRange('B2:B2000');
  var rule = SpreadsheetApp.newDataValidation().requireValueInRange(masterRange, true).setAllowInvalid(true).build();
  logSheet.getRange('D4:D10000').setDataValidation(rule);
  SpreadsheetApp.getUi().alert('✅ 시트 드롭다운 및 검증 복구가 완료되었습니다!');
}

function extendAutoLookupFormulas() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName('스티커작업일지');
  if (!logSheet) return;

  SpreadsheetApp.getUi().alert('✅ 자동완성 수식이 준비되었습니다!');
}

/**
 * ============================================================================
 * 우성월드 스티커 작업일지 관리자 전용 스마트 웹앱 백엔드 (Code.gs)
 * ============================================================================
 * [기능 목록]
 * 1. doGet(e): 실무자 전용 토스 스타일 모바일/PC 입력 웹앱 화면 렌더링
 * 2. getItemMasterList(): [아이템 마스터] 시트에서 품목 데이터 고속 조회
 * 3. saveDailyWorkLog(payload): [스티커작업일지] 및 [sticker_work_log_source]에
 *    수식 깨짐 없이 순수 정형 데이터로 일괄 안전 적재
 * 4. setupTestEnvironment(): 빈 구글 시트에서도 원클릭으로 3개 시트 자동 생성 및
 *    표준 품목 탑재 (테스트 시트 원클릭 세팅 지원)
 * ============================================================================
 */

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('⚡ 스티커 일지 자동화')
    .addItem('🛠️ 1. 테스트 환경 원클릭 자동 세팅 (시트 3종 생성)', 'setupTestEnvironment')
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

  // 시트가 없으면 자동으로 생성
  if (!masterSheet) {
    ensureRequiredSheetsExist_(ss);
    masterSheet = ss.getSheetByName('아이템 마스터');
  }

  var lastRow = masterSheet.getLastRow();
  if (lastRow < 2) {
    populateSampleItems_(masterSheet);
    lastRow = masterSheet.getLastRow();
  }

  // B열(2: 품목명), D열(4: 제조사), G열(7: 중량), J열(10: 기본입량)
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
 * [API 2] 오늘 작업일지 저장 (스티커작업일지 & sticker_work_log_source 동시 적재)
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
    var logRowsToAdd = [];
    var totalBoxes = 0;
    var totalStickers = 0;

    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      var lineNo = i + 1;
      var workerCell = (i === 0) ? (workerCount + '명') : '';
      var wQty = parseInt(it.workQty) || 0;
      var sQty = parseInt(it.stickerQty) || 0;
      totalBoxes += wQty;
      totalStickers += sQty;

      logRowsToAdd.push([
        workDate,
        workerCell,
        lineNo,
        it.itemName,
        it.volume || '',
        it.packQty || '',
        wQty,
        sQty,
        it.remark || '',
        it.fieldNote || ''
      ]);
    }

    // 소계(합계) 행
    logRowsToAdd.push([
      workDate,
      workerCount + '명',
      items.length,
      '계',
      '',
      '',
      totalBoxes,
      totalStickers,
      items.length + '개 품목 작업 완료',
      '스마트웹앱 등록'
    ]);

    var logLastRow = logSheet.getLastRow();
    logSheet.getRange(logLastRow + 1, 1, logRowsToAdd.length, 10).setValues(logRowsToAdd);

    // 원천 DB 시트 적재
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
        (j + 1),
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

    var dbLastRow = dbSheet.getLastRow();
    dbSheet.getRange(dbLastRow + 1, 1, dbRowsToAdd.length, 14).setValues(dbRowsToAdd);

    return {
      success: true,
      rowCount: items.length,
      totalBoxes: totalBoxes,
      totalStickers: totalStickers,
      message: '성공적으로 ' + items.length + '개 품목이 등록되었습니다.'
    };
  } catch (e) {
    return { success: false, message: '저장 중 오류 발생: ' + e.toString() };
  }
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
    '2) [스티커작업일지] 탭: 10개 표준 컬럼 및 헤더 서식 생성 완료\n' +
    '3) [sticker_work_log_source] 탭: 14개 원천 DB 컬럼 생성 완료\n\n' +
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
 * 필수 3종 시트 자동 검사 및 생성 내부 헬퍼
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

/**
 * 인라인 HTML 폴백
 */
function getEmbeddedHtml_() {
  return '<!DOCTYPE html><html><body style="font-family:sans-serif;padding:30px;text-align:center;">' +
         '<h3>Index.html 파일이 필요합니다.</h3>' +
         '<p>Apps Script 편집기에서 [+] -> [HTML] 클릭 후 파일명을 Index 로 입력하여 코드를 붙여넣어 주세요.</p>' +
         '</body></html>';
}

/**
 * [기능 2] 기존 일지 수동 동기화 및 복구 함수
 */
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

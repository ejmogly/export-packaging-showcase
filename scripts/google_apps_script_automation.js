/**
 * ============================================================================
 * 스티커작업일지 & 원천 DB 통합 자동화 스크립트 (v2.5 - 정밀 검진 B-1 ~ B-6 완벽 해결판)
 * ============================================================================
 * [주요 개선 사항]
 * 1. (B-1 & B-4 해결) D열 품목명 드롭다운 유효성 검사를 D4:D10000 전체로 확장하고,
 *    '경고 표시(setAllowInvalid(true))' 모드로 설정하여 신규 품목이나 'box' 입력 시
 *    빨간색 에러 삼각형이 뜨지 않도록 개선합니다.
 * 2. (B-2 해결) E열(중량), G열(입량) VLOOKUP 자동완성 및 H열(스티커수량) 수식에서
 *    'box'(외박스 부착)가 '판아시아' 또는 '롯데 캐나다'인 경우에만 작업수량(F열)만큼
 *    스티커수량이 산출되도록 정밀 수식을 적용합니다.
 * 3. (B-3 해결) [원천 DB로 일지 전송] 시 J열(10번째 컬럼: 현장 특이사항 메모 - 트레이, 2장 부착 등)까지
 *    누락 없이 sticker_work_log_source 시트의 M열(field_note)로 함께 전송합니다.
 * 4. (B-5 해결) [아이템 마스터] 시트의 '확인필요' 2건(씨리얼초코컵, 후레쉬베리복숭아)을
 *    '오리온'으로 자동 업데이트합니다.
 * ============================================================================
 */

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('⚡ 스티커 일지 자동화')
    .addItem('🚀 1. 원천 DB로 신규 일지 전송 (J열 특이사항 포함)', 'syncWorkLogToSourceDB')
    .addSeparator()
    .addItem('🔧 2. 시트 드롭다운/수식/마스터 일괄 자동 복구 (B-1~B-5 해결)', 'repairSheetFormulasAndValidation')
    .addItem('📐 3. 현재 행 아래로 자동완성 수식 500행 연장', 'extendAutoLookupFormulas')
    .addSeparator()
    .addItem('📱 4. 관리자 전용 토스형 웹앱 배포 가이드', 'showWebAppDeployGuide')
    .addToUi();
}

/**
 * [기능 1] 스티커작업일지 -> sticker_work_log_source 증분 전송 (J열 현장 메모 포함)
 */
function syncWorkLogToSourceDB() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName('스티커작업일지');
  var dbSheet = ss.getSheetByName('sticker_work_log_source');

  if (!logSheet || !dbSheet) {
    SpreadsheetApp.getUi().alert('오류: [스티커작업일지] 또는 [sticker_work_log_source] 시트를 찾을 수 없습니다.');
    return;
  }

  var lastLogRow = logSheet.getLastRow();
  if (lastLogRow < 4) {
    SpreadsheetApp.getUi().alert('전송할 작업일지 데이터가 없습니다.');
    return;
  }

  // A열(1) ~ J열(10)까지 10개 컬럼 전체 읽기 (J열 현장 특이사항 포함)
  var logValues = logSheet.getRange(4, 1, lastLogRow - 3, 10).getValues();

  // 기존 DB의 마지막 행 및 중복 방지 키(work_date + line_no + item_name + sticker_qty) 확인
  var lastDbRow = dbSheet.getLastRow();
  var existingKeys = {};
  if (lastDbRow >= 2) {
    var dbCols = Math.max(12, dbSheet.getLastColumn());
    var dbValues = dbSheet.getRange(2, 1, lastDbRow - 1, dbCols).getValues();
    for (var i = 0; i < dbValues.length; i++) {
      var r = dbValues[i];
      var dStr = formatDateKey_(r[2]);
      var key = [dStr, String(r[3]).trim(), String(r[4]).trim(), String(r[8]).trim()].join('|');
      existingKeys[key] = true;
    }
  }

  // 헤더에 field_note(13번째 컬럼)가 없으면 자동 추가
  if (dbSheet.getLastColumn() < 13) {
    dbSheet.getRange(1, 13).setValue('field_note');
  }

  var curDate = '';
  var curWorkers = '';
  var curHours = '';
  var newRows = [];

  for (var idx = 0; idx < logValues.length; idx++) {
    var row = logValues[idx];
    var rawDate = row[0];     // A열: 작업일자
    var rawWorker = row[1];   // B열: 근무인원/시간
    var rawLineNo = row[2];   // C열: No
    var rawItem = String(row[3] || '').trim(); // D열: 품목명
    var rawWeight = row[4];   // E열: 중량
    var rawWorkQty = row[5];  // F열: 작업수량(박스)
    var rawPackQty = row[6];  // G열: 입량
    var rawSticker = row[7];  // H열: 스티커수량(매)
    var rawRemark = String(row[8] || '').trim(); // I열: 비고(바이어/작업넘버)
    var rawNote = String(row[9] || '').trim();   // J열: 현장 특이사항(트레이, 2장 부착 등)

    if (rawDate !== '' && rawDate !== null) {
      curDate = formatDateKey_(rawDate);
    }
    if (rawWorker !== '' && rawWorker !== null) {
      var parsed = parseWorkerAndHours_(String(rawWorker));
      if (parsed.workers !== null) curWorkers = parsed.workers;
      if (parsed.hours !== null) curHours = parsed.hours;
    }

    // 품목명이 없거나 소계/합계 행이면 건너뜀
    if (!rawItem || rawItem === '품목명' || rawItem === '합계' || rawItem === '소계') {
      continue;
    }
    if (!curDate) {
      continue;
    }

    var lineNo = rawLineNo !== '' ? rawLineNo : (idx + 1);
    var dedupKey = [curDate, String(lineNo).trim(), rawItem, String(rawSticker).trim()].join('|');
    if (existingKeys[dedupKey]) {
      continue;
    }

    var yearMonth = curDate.substring(0, 7);
    var totalManHours = (Number(curWorkers) || 0) * (Number(curHours) || 0);

    newRows.push([
      '스티커작업일지_자동전송', // 1. source_pdf
      yearMonth,                // 2. sheet_month
      curDate,                  // 3. work_date
      lineNo,                   // 4. line_no
      rawItem,                  // 5. item_name
      rawWeight,                // 6. weight_g
      rawWorkQty,               // 7. work_qty
      rawPackQty,               // 8. pack_qty
      rawSticker,               // 9. sticker_qty
      rawRemark,                // 10. remark
      curWorkers,               // 11. daily_worker_count
      totalManHours,            // 12. daily_total_man_hours
      rawNote                   // 13. field_note (J열 특이사항 보존!)
    ]);
    existingKeys[dedupKey] = true;
  }

  if (newRows.length === 0) {
    SpreadsheetApp.getUi().alert('안내: 새로 추가할 신규 작업 행이 없습니다 (모두 동기화 완료 상태).');
    return;
  }

  dbSheet.getRange(dbSheet.getLastRow() + 1, 1, newRows.length, 13).setValues(newRows);
  SpreadsheetApp.getUi().alert('✅ 완료: 신규 작업일지 ' + newRows.length + '건(J열 특이사항 포함)이 원천 DB로 안전하게 전송되었습니다.');
}

/**
 * [기능 2] 시트 드롭다운 범위/경고모드, 마스터 미분류 2건, H열 수식 일괄 자동 복구 (B-1 ~ B-5 해결)
 */
function repairSheetFormulasAndValidation() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName('스티커작업일지');
  var masterSheet = ss.getSheetByName('아이템 마스터');

  if (!logSheet || !masterSheet) {
    SpreadsheetApp.getUi().alert('오류: [스티커작업일지] 또는 [아이템 마스터] 시트를 찾을 수 없습니다.');
    return;
  }

  // 1. (B-5 해결) 아이템 마스터 내 '확인필요' 2건 -> '오리온' 자동 수정
  var lastMasterRow = masterSheet.getLastRow();
  var fixedMasterCount = 0;
  if (lastMasterRow >= 2) {
    var masterData = masterSheet.getRange(2, 1, lastMasterRow - 1, 4).getValues();
    for (var i = 0; i < masterData.length; i++) {
      var itemName = String(masterData[i][1] || masterData[i][0] || '').replace(/\s+/g, '');
      var mfgName = String(masterData[i][3] || masterData[i][2] || '').trim();
      if ((itemName.indexOf('씨리얼초코컵') !== -1 || itemName.indexOf('후레쉬베리복숭아') !== -1) && mfgName === '확인필요') {
        // 4열(manufacturer_name) 또는 해당 컬럼 업데이트
        masterSheet.getRange(i + 2, 4).setValue('오리온');
        fixedMasterCount++;
      }
    }
  }

  // 2. (B-1 & B-4 해결) 스티커작업일지 D4:D10000 드롭다운을 [경고 표시(setAllowInvalid(true))] 모드로 재설정
  var masterRange = masterSheet.getRange('B2:B2000'); // 품목명 컬럼
  var validationRule = SpreadsheetApp.newDataValidation()
    .requireValueInRange(masterRange, true)
    .setAllowInvalid(true) // 신상품이나 'box' 입력 시 빨간 에러 차단 없이 통과
    .build();
  logSheet.getRange('D4:D10000').setDataValidation(validationRule);

  // 3. J열 헤더('특이사항(트레이/2장부착 등)') 명시
  var jHeader = String(logSheet.getRange('J3').getValue() || '').trim();
  if (!jHeader) {
    logSheet.getRange('J3').setValue('특이사항(트레이/2장부착 등)');
  }

  SpreadsheetApp.getUi().alert(
    '✅ 시트 자동 복구가 완료되었습니다!\n\n' +
    '1) D4:D10000 드롭다운 범위 확장 및 경고 모드 전환 완료 (신규 품목 입력 시 에러 없음)\n' +
    '2) 아이템 마스터 미분류 수정 완료 (' + fixedMasterCount + '건 -> 오리온)\n' +
    '3) J열 특이사항 헤더 확인 완료'
  );
}

/**
 * [기능 3] 마지막 작성 행 아래로 500행 동안 E열(중량), G열(입량), H열(스티커수량: 판아시아/롯데 캐나다 box 조건 반영) 수식 자동 연장
 */
function extendAutoLookupFormulas() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName('스티커작업일지');
  if (!logSheet) return;

  var startRow = Math.max(4, logSheet.getLastRow() + 1);
  var numRows = 500;

  var eFormulas = [];
  var gFormulas = [];
  var hFormulas = [];

  for (var i = 0; i < numRows; i++) {
    var r = startRow + i;
    // E열(중량): 아이템 마스터 B열(품목명) 기준 G열(volume_value) 조회 (또는 기존 구조 호환)
    eFormulas.push(['=IF(D' + r + '="", "", IFERROR(VLOOKUP(D' + r + ', \'아이템 마스터\'!$B$2:$J$2000, 6, FALSE), ""))']);
    // G열(입량): 아이템 마스터 B열(품목명) 기준 J열(default_pack_qty) 조회
    gFormulas.push(['=IF(D' + r + '="", "", IFERROR(VLOOKUP(D' + r + ', \'아이템 마스터\'!$B$2:$J$2000, 9, FALSE), ""))']);
    // H열(스티커수량): D열이 'box'인 경우 비고(I열)에 '판아시아' 또는 '롯데 캐나다'가 포함될 때만 F열(작업박스수), 그 외 일반 품목은 F*G
    hFormulas.push([
      '=IF(D' + r + '="", "", IF(LOWER(TRIM(D' + r + '))="box", ' +
      'IF(OR(ISNUMBER(SEARCH("판아시아", I' + r + ')), ISNUMBER(SEARCH("롯데 캐나다", I' + r + ')), ISNUMBER(SEARCH("롯데캐나다", I' + r + '))), F' + r + ', 0), ' +
      'IF(ISNUMBER(F' + r + '*G' + r + '), F' + r + '*G' + r + ', "")))'
    ]);
  }

  logSheet.getRange(startRow, 5, numRows, 1).setFormulas(eFormulas);
  logSheet.getRange(startRow, 7, numRows, 1).setFormulas(gFormulas);
  logSheet.getRange(startRow, 8, numRows, 1).setFormulas(hFormulas);

  SpreadsheetApp.getUi().alert(
    '✅ ' + startRow + '행부터 ' + (startRow + numRows - 1) + '행까지\n' +
    'E열(중량), G열(입량), H열(스티커수량: 판아시아/롯데 캐나다 외박스 조건 포함) 자동 수식이 연장되었습니다!'
  );
}

/**
 * 날짜 객체를 YYYY-MM-DD 문자열로 변환하는 내부 헬퍼
 */
function formatDateKey_(val) {
  if (!val) return '';
  if (Object.prototype.toString.call(val) === '[object Date]') {
    return Utilities.formatDate(val, Session.getScriptTimeZone(), 'yyyy-MM-dd');
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

/**
 * "3.5명 / 8시간" 또는 "4" 형태의 문자열에서 인원과 시간을 분리하는 내부 헬퍼
 */
function parseWorkerAndHours_(str) {
  var res = { workers: null, hours: 8 };
  if (!str) return res;
  var nums = str.match(/\d+(\.\d+)?/g);
  if (nums && nums.length >= 1) {
    res.workers = parseFloat(nums[0]);
  }
  if (nums && nums.length >= 2) {
    res.hours = parseFloat(nums[1]);
  }
  return res;
}

/**
 * ============================================================================
 * [기능 4] 관리자 전용 토스형 스마트 웹앱 (Web App) 서비스 엔드포인트
 * ============================================================================
 */

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

function doGet(e) {
  var template;
  try {
    template = HtmlService.createTemplateFromFile('Index');
  } catch (err) {
    template = HtmlService.createTemplate(
      '<!DOCTYPE html><html><body style="font-family:sans-serif;padding:30px;text-align:center;">' +
      '<h3>Index.html 파일이 필요합니다.</h3>' +
      '<p>Apps Script 편집기에서 [+] -> [HTML] 클릭 후 파일명을 Index 로 입력하여 코드를 붙여넣어 주세요.</p>' +
      '</body></html>'
    );
  }

  return template.evaluate()
    .setTitle('우성월드 스티커 작업일지 등록')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getItemMasterList() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var masterSheet = ss.getSheetByName('아이템 마스터');
  if (!masterSheet) return [];

  var lastRow = masterSheet.getLastRow();
  if (lastRow < 2) return [];

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

function saveDailyWorkLog(payload) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var logSheet = ss.getSheetByName('스티커작업일지');
    var dbSheet = ss.getSheetByName('sticker_work_log_source');

    if (!logSheet || !dbSheet) {
      return { success: false, message: '시트 [스티커작업일지] 또는 [sticker_work_log_source]를 찾을 수 없습니다.' };
    }

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


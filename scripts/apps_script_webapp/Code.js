/**
 * ============================================================================
 * 우성월드 스티커 작업일지 관리자 전용 스마트 웹앱 백엔드 (Code.gs)
 * ============================================================================
 * 1. doGet(e): 실무자 전용 토스 스타일 모바일/PC 입력 웹앱 화면 렌더링
 * 2. getItemMasterList(): [아이템 마스터] 시트에서 700여 개 품목 데이터 고속 조회
 * 3. saveDailyWorkLog(payload): [스티커작업일지] 및 [sticker_work_log_source]에
 *    수식 깨짐 없이 순수 정형 데이터로 일괄 안전 적재
 * ============================================================================
 */

function doGet(e) {
  var template;
  try {
    template = HtmlService.createTemplateFromFile('Index');
  } catch (err) {
    // Index.html 파일이 별도로 없는 경우를 대비한 안전 폴백
    template = HtmlService.createTemplate(getEmbeddedHtml_());
  }

  return template.evaluate()
    .setTitle('우성월드 스티커 작업일지 등록')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * [API 1] 아이템 마스터 품목 목록 조회 (클라이언트 검색용 캐시)
 */
function getItemMasterList() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var masterSheet = ss.getSheetByName('아이템 마스터');
  if (!masterSheet) {
    return [];
  }

  var lastRow = masterSheet.getLastRow();
  if (lastRow < 2) return [];

  // B열(2: 품목명), D열(4: 제조사), G열(7: 중량), J열(10: 기본입량) 읽기
  var rangeData = masterSheet.getRange(2, 1, lastRow - 1, 10).getValues();
  var items = [];

  for (var i = 0; i < rangeData.length; i++) {
    var r = rangeData[i];
    var itemName = String(r[1] || '').trim();
    if (!itemName) continue;

    var mfgName = String(r[3] || '').trim();
    var volume = r[6] !== '' && r[6] !== null ? String(r[6]).trim() : '';
    var packQty = parseInt(r[9]) || 0;

    items.push({
      name: itemName,
      mfg: mfgName,
      volume: volume,
      packQty: packQty
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
    var logSheet = ss.getSheetByName('스티커작업일지');
    var dbSheet = ss.getSheetByName('sticker_work_log_source');

    if (!logSheet || !dbSheet) {
      return { success: false, message: '시트 [스티커작업일지] 또는 [sticker_work_log_source]를 찾을 수 없습니다.' };
    }

    var workDate = payload.workDate;       // "YYYY-MM-DD"
    var workerCount = payload.workerCount; // 11
    var workHours = payload.workHours;     // 8.0
    var items = payload.items;             // Array of item objects

    if (!items || items.length === 0) {
      return { success: false, message: '등록할 작업 품목이 없습니다.' };
    }

    var workMonth = workDate.substring(0, 7); // "YYYY-MM"

    // 1. [스티커작업일지] 시트에 행 추가
    // 컬럼 순서: A:작업일, B:작업인원, C:no, D:품목, E:중량, F:입량, G:작업수량, H:스티커수량, I:비고, J:특이사항
    var logRowsToAdd = [];
    var totalBoxes = 0;
    var totalStickers = 0;

    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      var lineNo = i + 1;
      var workerCell = (i === 0) ? (workerCount + '명') : ''; // 첫 행에 인원 명시
      var wQty = parseInt(it.workQty) || 0;
      var sQty = parseInt(it.stickerQty) || 0;
      totalBoxes += wQty;
      totalStickers += sQty;

      logRowsToAdd.push([
        workDate,             // A: 작업일
        workerCell,           // B: 작업인원
        lineNo,               // C: no
        it.itemName,          // D: 품 목
        it.volume || '',      // E: 중량
        it.packQty || '',     // F: 입량
        wQty,                 // G: 작업수량(박스)
        sQty,                 // H: 스티커수량(매)
        it.remark || '',      // I: 비고 (바이어/오더코드)
        it.fieldNote || ''    // J: 특이사항(트레이/2장부착 등)
      ]);
    }

    // 소계(합계) 행 추가
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
    var logStartRow = logLastRow + 1;
    logSheet.getRange(logStartRow, 1, logRowsToAdd.length, 10).setValues(logRowsToAdd);

    // 2. [sticker_work_log_source] 원천 DB 시트에 행 추가
    // 컬럼: source_file_name, page_no, work_month, work_date, worker_count, line_no, item_name, volume, pack_qty, work_qty, sticker_qty, remark, is_verified, verified_note
    var dbRowsToAdd = [];
    for (var j = 0; j < items.length; j++) {
      var itm = items[j];
      var noteText = itm.fieldNote ? ('스마트웹앱: ' + itm.fieldNote) : '스마트웹앱 자동등록';

      dbRowsToAdd.push([
        '스마트웹앱_작성',           // 0: source_file_name
        1,                          // 1: page_no
        workMonth,                  // 2: work_month
        workDate,                   // 3: work_date
        workerCount,                // 4: worker_count
        (j + 1),                    // 5: line_no
        itm.itemName,               // 6: item_name
        itm.volume || '',           // 7: volume
        itm.packQty || 0,           // 8: pack_qty
        parseInt(itm.workQty) || 0, // 9: work_qty
        parseInt(itm.stickerQty) || 0, // 10: sticker_qty
        itm.remark || '',           // 11: remark
        true,                       // 12: is_verified
        noteText                    // 13: verified_note
      ]);
    }

    var dbLastRow = dbSheet.getLastRow();
    var dbStartRow = dbLastRow + 1;
    dbSheet.getRange(dbStartRow, 1, dbRowsToAdd.length, 14).setValues(dbRowsToAdd);

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
 * 인라인 HTML 폴백 (Index.html을 별도로 만들지 않고 단독 파일로 실행할 때 사용)
 */
function getEmbeddedHtml_() {
  return '<!DOCTYPE html><html><body style="font-family:sans-serif;padding:20px;text-align:center;">' +
         '<h3>Index.html 파일을 프로젝트에 추가해 주세요.</h3>' +
         '<p>Apps Script 편집기에서 [+] -> [HTML] 클릭 후 파일명을 Index 로 입력하시면 됩니다.</p>' +
         '</body></html>';
}

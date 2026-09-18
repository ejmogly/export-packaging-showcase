# 📖 Data Dictionary & Validation Rules

## 1. Bronze Layer (Raw Source Data)

| 컬럼명 | 표준 한글 용어 | 데이터 타입 | 필수 여부 | 유효성 검증 규칙 / 허용 범위 | 예시값 |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `source_file_name` | 원천 파일명 | `VARCHAR` | Y | `TalkFile_*.pdf` 형식 | `TalkFile_202604스티커작업실적.pdf` |
| `page_no` | PDF 일지 페이지 | `INTEGER` | Y | $1 \le \text{page\_no} \le 100$ | `1` |
| `work_month` | 작업 연월 | `VARCHAR(7)` | Y | `YYYY-MM` 형식 | `2026-04` |
| `work_date` | 작업 일자 | `DATE` | Y | `YYYY-MM-DD` 형식 | `2026-04-03` |
| `worker_count` | 투입 인원 수 | `FLOAT` | Y | $\ge 0$ (0인 경우 미기재로 간주되어 보정 필요) | `8.0` |
| `line_no` | 일지 내 행 번호 | `INTEGER` | Y | $\ge 1$ | `1` |
| `item_name` | 수기 품목명 | `VARCHAR` | Y | 공란 불가, 공백 및 오타 존재 가능 | `피카픽`, `초코파이`, `the빠새` |
| `volume` | 중량/규격 | `VARCHAR` | N | 숫자 또는 배수 표기 (g, ml, L, 팩) | `45`, `100x10`, `1.5` |
| `pack_qty` | **입량** | `INTEGER` | Y | $\ge 1$ (한 박스에 들어가는 낱개 수) | `24`, `16`, `12` |
| `work_qty` | **작업수량** | `INTEGER` | Y | $\ge 1$ (스티커 부착 작업한 총 박스 수) | `560`, `100` |
| `sticker_qty` | **스티커수량** | `INTEGER` | Y | 원칙적으로 $\text{입량} \times \text{작업수량}$ | `13440` |
| `remark` | 비고 / 바이어 / 오더 | `VARCHAR` | N | 바이어명, 수출국가, 오더번호 등 | `판아시아 오스트리아`, `527`, `희창물산` |
| `is_verified` | 검수 완료 여부 | `BOOLEAN` | Y | `TRUE` / `FALSE` | `TRUE` |
| `verified_note` | 검수 특이사항 메모 | `VARCHAR` | N | 수량 불일치, 인원 보정 사유 기록 | `사용자 검수 통과`, `원본값 유지, QC mismatch 예상` |

---

## 2. Silver Layer (Cleaned & Enriched Data)

| 컬럼명 | 표준 한글 용어 | 데이터 타입 | 생성 로직 및 비즈니스 규칙 |
| :--- | :--- | :--- | :--- |
| `normalized_item_name` | 표준 제품명 | `VARCHAR` | 지능형 정규화 엔진(4단계: Rule -> Alias -> Master -> Fuzzy) 결과 |
| `manufacturer` | 제조사 | `VARCHAR` | `item_master.csv` 조인 (예: `오리온`, `롯데웰푸드`, `해태제과`, `광동제약`) |
| `category_1` | 대분류 | `VARCHAR` | `item_master.csv` 조인 (예: `과자`, `음료`, `냉동식품`) |
| `category_2` | 중분류 | `VARCHAR` | `item_master.csv` 조인 (예: `스낵`, `비스킷/쿠키`, `초콜릿`, `만두`) |
| `standard_volume` | 표준중량/규격 | `VARCHAR` | `item_master.csv` 단위 표준화 (예: `72g`, `1.5L`, `238ml x 12`) |
| `buyer_normalized` | 정규화 바이어/국가 | `VARCHAR` | `remark` 정규화 (예: `판아시아 오스트리아`, `007(캐나다 TB)`, `희창물산`) |
| `export_country` | 수출 대상국 | `VARCHAR` | 비고/거래처에서 파싱된 표준 국가명 (예: `오스트리아`, `캐나다`, `독일`, `미국`, `몽골`) |
| `calc_sticker_qty` | 계산 스티커 수량 | `INTEGER` | $\text{입량(pack\_qty)} \times \text{작업수량(work\_qty)}$ |
| `qty_mismatch_flag` | 수량 불일치 플래그 | `BOOLEAN` | `calc_sticker_qty != sticker_qty` 시 `True` (전체 3,188건 중 404건 감지) |
| `unmatched_item_flag` | 품목 마스터 미매칭 플래그 | `BOOLEAN` | `item_master`에 등록되지 않은 품목일 경우 `True` (현재 0건 완료) |
| `difficulty_tier` | 난이도 등급 | `VARCHAR` | 박스 입수량 기준 분류 (`쉬움`: $\le 12$, `보통`: $13 \sim 30$, `어려움`: $\ge 31$) |
| `fuzzy_suggested_item` | 퍼지 매칭 추천 품목 | `VARCHAR` | 미매칭 시 유사도 80% 이상의 가장 가까운 표준 품목명 |
| `fuzzy_score` | 유사도 점수 | `FLOAT` | 0.0 ~ 1.0 (1.0 = 완전 일치) |
| `effective_worker_count` | 보정 투입 인원 | `FLOAT` | `worker_count == 0`일 경우 인력계획 또는 전후일 평균으로 자동 보정 |
| `total_worker_hours` | 총 투입 공수 | `FLOAT` | $\text{effective\_worker\_count} \times 8.0 + \text{overtime\_hours}$ (누적 Man-Hours) |

---

## 3. Gold Layer (Analytics Data Marts)

### 3.1 `daily_productivity_mart` (일자별 생산성 마트)
* **Grain**: `work_date` (1 Day = 1 Row)
* **Metrics**:
  * `total_stickers`: 일일 총 부착 스티커 수 ($\sum \text{sticker\_qty}$)
  * `total_boxes`: 일일 총 작업 박스 수 ($\sum \text{work\_qty}$)
  * `worker_count`: 당일 투입 인원 수
  * `total_worker_hours`: 당일 총 공수 (Man-Hours)
  * `stickers_per_man_hour`: $\frac{\text{total\_stickers}}{\text{total\_worker\_hours}}$ (시간당 부착 스티커 속도)
  * `boxes_per_man_hour`: $\frac{\text{total\_boxes}}{\text{total\_worker\_hours}}$ (시간당 박스 처리 속도)
  * `stickers_per_worker_daily`: $\frac{\text{total\_stickers}}{\text{effective\_worker\_count}}$ (1인당 일일 처리량)

### 3.2 `item_difficulty_mart` (품목별 난이도 마트)
* **Grain**: `normalized_item_name`
* **Metrics**:
  * `total_orders`: 총 작업 횟수 (건수)
  * `total_boxes`: 누적 박스 수
  * `total_stickers`: 누적 스티커 수
  * `avg_pack_qty`: 평균 입수량 (높을수록 낱개 포장 난이도 증가)
  * `difficulty_tier`: 입수량 기준 3단계 난이도 등급 (`쉬움`, `보통`, `어려움`)

### 3.3 `buyer_summary_mart` (바이어별 실적 마트)
* **Grain**: `buyer_normalized`
* **Metrics**:
  * `order_count`: 주문 건수
  * `active_days`: 가동 일수
  * `total_boxes`: 바이어별 총 출하 박스 수
  * `total_stickers`: 바이어별 총 스티커 수량
  * `allocated_man_hours`: 비례 배분된 투입 공수 (인·시)
  * `distinct_items`: 취급 SKU 품목 수
  * `sticker_share_pct`: 전체 출하량 대비 스티커 점유율 (%)
  * `box_share_pct`: 전체 출하량 대비 박스 점유율 (%)
  * `top_items`: 가장 많이 작업한 상위 2개 품목
  * `buyer_health_status`: MoM/QoQ 변동 기반 4대 건강도 (`🚀 고성장`, `🟢 안정/유지`, `⚠️ 이탈 주의`, `🆕 신규/재개`)

### 3.4 `country_summary_mart` (수출 대상국별 마트)
* **Grain**: `export_country`
* **Metrics**:
  * `export_region`: 소속 글로벌 권역 (북미, 서유럽, 동유럽, 동아시아, 동남아, 오세아니아)
  * `order_count`: 주문 건수
  * `active_days`: 가동 일수
  * `total_boxes`: 국가별 총 출하 박스 수
  * `total_stickers`: 국가별 총 스티커 수량
  * `allocated_man_hours`: 국가별 투입 공수 (인·시)
  * `distinct_buyers`: 거래 바이어 수
  * `distinct_items`: 취급 SKU 품목 수
  * `sticker_share_pct`: 전체 대비 스티커 점유율 (%)
  * `top_items`: 해당 국가 선적 상위 3개 품목

### 3.5 `category_summary_mart` (식품 카테고리별 마트)
* **Grain**: `category_1, category_2`
* **Metrics**:
  * `item_count`: 등록 품목 수
  * `order_count`: 누적 작업 건수
  * `total_boxes`: 누적 출하 박스 수
  * `total_stickers`: 누적 부착 스티커 수량
  * `allocated_man_hours`: 누적 투입 공수 (인·시)
  * `stickers_per_hour`: 카테고리별 시간당 평균 부착 속도 (매/hr)

### 3.6 `financial_margin_mart` (임가공 단가 & 마진 채산성 마트)
* **Grain**: `normalized_item_name` 또는 `buyer_normalized`
* **Metrics**:
  * `revenue`: 3대 계약단가제 적용 총 매출 (원)
  * `labor_cost`: 투입 공수 × 시급 (기본 13,000원) 기반 인건비 원가 (원)
  * `gross_profit`: $\text{revenue} - \text{labor\_cost}$ (공정 총이익)
  * `margin_rate`: $\frac{\text{gross\_profit}}{\text{revenue}} \times 100$ (마진율 %)
  * `margin_per_box`: $\frac{\text{gross\_profit}}{\text{total\_boxes}}$ (박스당 공정 마진 원)

---

## 4. 데이터 품질(DQ) 감사 및 무결성 판별 규칙

### 4.1 수량 정합성 감사 규칙 (87.33% 무결성 통과율)
* **원칙**: 모든 포장 작업 행은 $\text{입량(pack\_qty)} \times \text{작업수량(work\_qty)} = \text{스티커수량(sticker\_qty)}$을 만족해야 함.
* **통계 결과**:
  * **정상 일치 (무결성 통과)**: **2,784건 (87.33%)**
  * **수량 불일치 감지**: **404건 (12.67%)**
* **불일치(404건) 주요 발생 사유 및 현장 처리 가이드**:
  1. **현장 수기 편의 기재**: 낱개 포장 묶음(예: 3개입 1세트)에 대해 스티커 1매만 부착하고 입량은 낱개 수(30개)로 적어 발생.
  2. **여분 라벨 및 손실분(Scrap) 포함**: 작업 불량이나 로스분을 포함하여 스티커 수량을 실제보다 넉넉히 기록한 경우.
  3. **OCR 및 수기 오독**: 필기체 일지 스캔 시 '1'과 '7', '0'과 '8' 등의 OCR 오인식.
* **시스템 보정 정책**:
  * 대시보드 실적 집계 시 **현장 작업자가 직접 기재한 실제 라벨 부착 실적인 `sticker_qty`를 우선 기준으로 채택**하여 임가공 공임 및 출하 물량의 오차를 원천 차단함.
  * 서브탭 5.1(정밀 검수실)에서 404건 불일치 데이터를 전수 분리하여 담당자가 즉시 원클릭으로 감사할 수 있도록 제공.


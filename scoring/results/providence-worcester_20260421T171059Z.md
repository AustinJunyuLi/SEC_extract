# Diff report — providence-worcester
_Generated 2026-04-21T17:10:59+00:00Z. This is a human-review aid, not a grade._

## Summary
- matched rows: **21**
- AI-only rows: **3**
- Alex-only rows: **3**
- cardinality mismatches: **5**
- deal-level disagreements: **3**
- field disagreements: **9** (bid_date_rough=5, bid_type=2, bidder_type=2)
- Alex-self-flagged rows hit: **0** (expected to diverge; see reference/alex/alex_flagged_rows.json)

## Deal-level disagreements
- **TargetName** — ai=`'Providence and Worcester Railroad Company'` · alex=`'PROVIDENCE & WORCESTER RR CO'`
- **Acquirer** — ai=`'Genesee & Wyoming Inc.'` · alex=`'GENESEE & WYOMING INC'`
- **DateEffective** — ai=`None` · alex=`'2016-11-01'`

## Matched-row divergences
### Matched: `Party E` · `Bid` · 2016-07-20
- AI BidderID 44 · Alex BidderID 8
  - **bid_date_rough** — ai=`'late July 2016'` · alex=`None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Matched: `Party C` · `Bid` · 2016-07-20
- AI BidderID 45 · Alex BidderID 10
  - **bid_date_rough** — ai=`'late July 2016'` · alex=`None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Matched: `Party F` · `Bid` · 2016-07-20
- AI BidderID 46 · Alex BidderID 11
  - **bidder_type** — ai=`{'base': 's', 'non_us': False, 'public': None}` · alex=`{'base': 'f', 'non_us': False, 'public': None}`
  - **bid_date_rough** — ai=`'late July 2016'` · alex=`None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Matched: `Party B` · `Bid` · 2016-07-20
- AI BidderID 47 · Alex BidderID 12
  - **bid_date_rough** — ai=`'late July 2016'` · alex=`None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Matched: `Party D` · `Bid` · 2016-07-20
- AI BidderID 48 · Alex BidderID 9
  - **bid_type** — ai=`'formal'` · alex=`'informal'`
  - **bid_date_rough** — ai=`'late July 2016'` · alex=`None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Matched: `G&W` · `Bid` · 2016-07-21
- AI BidderID 50 · Alex BidderID 15
  - **bid_type** — ai=`'formal'` · alex=`'informal'`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Matched: `Party F` · `DropTarget` · 2016-07-27
- AI BidderID 56 · Alex BidderID 27
  - **bidder_type** — ai=`{'base': 's', 'non_us': False, 'public': None}` · alex=`{'base': 'f', 'non_us': False, 'public': None}`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Cardinality mismatch: `NDA` residual bucket
- AI dates `['2016-03-30', '2016-07-05']` · Alex dates `[None]`
- AI rows `26` · Alex rows `2`
- AI BidderIDs `[4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 42]`
- Alex BidderIDs `[4, 19]`
- No field-level pairing attempted; counts differ within this residual event-type bucket.
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Cardinality mismatch: `Final Round Inf Ann` residual bucket
- AI dates `['2016-04-27', '2016-06-15']` · Alex dates `[None]`
- AI rows `2` · Alex rows `1`
- AI BidderIDs `[29, 41]`
- Alex BidderIDs `[3]`
- No field-level pairing attempted; counts differ within this residual event-type bucket.
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Cardinality mismatch: `Bid` residual bucket
- AI dates `['2016-05-25', '2016-08-01']` · Alex dates `['2016-08-01', '2016-08-02', None]`
- AI rows `10` · Alex rows `3`
- AI BidderIDs `[30, 31, 32, 33, 34, 35, 36, 37, 38, 58]`
- Alex BidderIDs `[1, 29, 30]`
- No field-level pairing attempted; counts differ within this residual event-type bucket.
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Cardinality mismatch: `Drop` residual bucket
- AI dates `['2016-08-02']` · Alex dates `['2016-06-01', '2016-07-22', '2016-08-12']`
- AI rows `1` · Alex rows `4`
- AI BidderIDs `[59]`
- Alex BidderIDs `[5, 20, 21, 34]`
- No field-level pairing attempted; counts differ within this residual event-type bucket.
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Cardinality mismatch: `Executed` residual bucket
- AI dates `['2016-08-12']` · Alex dates `['2016-07-20', '2016-08-15']`
- AI rows `1` · Alex rows `2`
- AI BidderIDs `[64]`
- Alex BidderIDs `[14, 36]`
- No field-level pairing attempted; counts differ within this residual event-type bucket.
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Date mismatch: `Party A` · `Bidder Interest`
- AI date `2015-11-15` · Alex date `2016-07-22` (AI id 1, Alex id 18)
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Date mismatch: `None` · `Target Sale`
- AI date `2015-11-22` · Alex date `2016-07-22` (AI id 2, Alex id 16)
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Date mismatch: `Greene Holcomb & Fisher LLC` · `IB`
- AI date `2016-01-27` · Alex date `None` (AI id 3, Alex id 17)
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Date mismatch: `None` · `Final Round Inf`
- AI date `2016-07-20` · Alex date `None` (AI id 49, Alex id 13)
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Date mismatch: `None` · `Final Round Ann`
- AI date `2016-07-27` · Alex date `None` (AI id 52, Alex id 22)
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

## AI-only rows
### AI-only (added by AI): `IOI Bidder low-1` · `DropBelowInf` · 2016-06-01
- BidderID 39 · bid_type `None` · per-share `None`
- source_page `36`: 'In view of the substantial amount of management time that would be required for management presentations, the Transaction Committee concluded that the two low bidders should be excluded from that proc…'
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### AI-only (added by AI): `IOI Bidder low-2` · `DropBelowInf` · 2016-06-01
- BidderID 40 · bid_type `None` · per-share `None`
- source_page `36`: 'In view of the substantial amount of management time that would be required for management presentations, the Transaction Committee concluded that the two low bidders should be excluded from that proc…'
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### AI-only (added by AI): `None` · `Auction Closed` · 2016-08-12
- BidderID 63 · bid_type `None` · per-share `None`
- source_page `39`: 'The Board determined that the G&W offer represented the superior proposal. At the request of the Board, representatives of BMO reviewed BMO’s financial analyses supporting its opinion to the Board as …'
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

## Alex-only rows
### Alex-only (AI missed): `G&W` · `None` · 2016-04-13
- BidderID 2 · bid_type `None` · per-share `None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Alex-only (AI missed): `2 parties` · `DropTarget` · 2016-06-01
- BidderID 6 · bid_type `None` · per-share `None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

### Alex-only (AI missed): `None` · `Final Round` · None
- BidderID 35 · bid_type `None` · per-share `None`
- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`

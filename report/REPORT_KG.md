# Báo cáo Day 19 — Flat RAG vs GraphRAG

**Họ tên:** Chu Minh Quân  **MSSV:** 2A202602709  **Ngày:** 05/10/2026

> Kỳ vọng và thang điểm: `SUBMISSION.md`. Mọi số liệu phải khớp với `ket_qua_benchmark_kg.txt`. Bản thiết kế ontology nộp riêng ở `report/ONTOLOGY.md`.

## 1. Chi phí (10 điểm)

Dán 2 bảng `Indexing` và `Querying` từ `ket_qua_benchmark_kg.txt`:

```text
== Indexing (one-off)
pipeline  calls    in_tok  out_tok       USD  seconds
flat        176         0        0   0.00000    219.4
graph       196     34619     5603   0.00000    426.0

== Querying (mean per question)
pipeline  recall  judge   in_tok  out_tok       USD  seconds
flat        0.51   1.33      696       76   0.00000     6.64
graph       0.94   1.83     5576      114   0.00000     7.03
```

| Chỉ số | Flat | Graph | Graph / Flat |
| --- | --- | --- | --- |
| Indexing USD | 0.0 | 0.0 | × 1.0 (do free tier) |
| Indexing giây | 219.4 | 426.0 | × 1.94 |
| Mỗi câu: USD | 0.0 | 0.0 | × 1.0 |
| Mỗi câu: giây | 6.64 | 7.03 | × 1.06 |
| Mỗi câu: in_tok | 696 | 5576 | × 8.01 |

**Chi phí tăng thêm đến từ đâu?** (2–3 câu)
> Chi phí và thời gian indexing tăng mạnh (hơn gấp đôi thời gian) chủ yếu do GraphRAG phải dùng LLM trích xuất từng entity và quan hệ cho mọi bài báo (20 bài). Với mỗi câu hỏi, số input tokens cao gấp 8 lần là do prompt của GraphRAG phải gánh thêm rất nhiều dữ kiện text từ Knowledge Graph (`context`) bên cạnh các chunks của Flat RAG.

## 2. Từng câu hỏi (10 điểm)

| Câu | Loại | Flat recall / judge | Graph recall / judge | Thắng | Vì sao (1 câu) |
| --- | --- | --- | --- | --- | --- |
| Q1 | single-hop-law | 1.00 / 2 | 1.00 / 2 | Hòa | Cả hai đều tìm thấy và trả lời đầy đủ thông tin từ một đoạn luật cụ thể trong KB. |
| Q2 | single-hop-news | 1.00 / 2 | 1.00 / 2 | Hòa | Thông tin tên bị cáo chỉ nằm ở một chunk trong một bài báo nên vector search của Flat RAG lấy được ngay. |
| Q3 | cross-kb | 0.33 / 1 | 1.00 / 2 | Graph | Câu hỏi yêu cầu biết mức án cơ bản nằm trong KB luật, mà chunk tin tức không có, phải nhờ Graph nối sang `Crime` để lấy. |
| Q4 | cross-kb | 0.33 / 1 | 0.67 / 1 | Graph | Tương tự Q3, Graph tìm được đúng Điều luật tuy nhiên lấy sai khoản phạt tối đa vì thiếu ontology về khối lượng. |
| Q5 | cross-kb-multi-hop | 0.40 / 1 | 1.00 / 2 | Graph | Graph dễ dàng nối thông tin loại tội và loại ma túy giữa các nguồn tin tức và luật để suy ra chính xác khoản luật áp dụng. |
| Q6 | aggregation | 0.00 / 1 | 1.00 / 2 | Graph | Flat RAG thất bại vì không thể tập hợp đủ các chunk rải rác trên toàn KB, trong khi Graph đi xuyên qua các `Case` liên quan đến `Substance` đó. |

## 3. Phân tích lỗi (20 điểm)

Chọn ít nhất 2 nhóm lỗi trong E1–E6 (`LAB_GUIDE.md` Bước 8.4). Sao chép khung dưới đây cho mỗi lỗi.

### Lỗi E1: Cầu nối gãy

- **Hiện tượng:** Có những vụ án trong tin tức nhưng không được nối với bất kỳ Điều luật nào, khiến GraphRAG không thể liên kết sang KB luật.
- **Bằng chứng:** 
```cypher
MATCH (k:Case) WHERE NOT (k)-[:CHARGED_WITH]->() RETURN k.name, k.doc_id
```

```text
{'k.name': 'Vụ vận chuyển vũ khí và chất nghi là ma túy tại Preah Sihanouk', 'k.doc_id': 'news-100260924145818945'}
{'k.name': 'Vụ tông cảnh sát giao thông tại An Giang', 'k.doc_id': 'news-100260926112415229'}
{'k.name': 'Triệt phá chuyên án A3-626P', 'k.doc_id': 'news-100261002184934505'}
```

- **Nguyên nhân:** Tên tội danh do LLM tự trích xuất từ bài báo không chuẩn xác hoặc bài báo chỉ kể lại sự việc (chưa có tội danh bị khởi tố cụ thể). Khi chạy qua hàm `link_entity`, các tội này không khớp được với danh sách tội chuẩn bên bộ luật, khiến node bị tách đôi.
- **Đề xuất sửa:** Sửa prompt trích xuất ở KG-2 để ép LLM phải ánh xạ sự kiện vào một hoặc nhiều tội danh trong danh sách cho sẵn; nếu không chắc chắn thì thiết lập một liên kết `SUSPECTED_OF` đến tội danh khả dĩ nhất để không làm mất cầu nối hoàn toàn. Tăng thêm ngưỡng fuzzy match.

### Lỗi E2: Thiếu ngữ cảnh luật

- **Hiện tượng:** Câu trả lời sai mức phạt tối đa hoặc khung hình phạt dù graph có Điều luật đó (điển hình ở câu Q4).
- **Bằng chứng:** 

```cypher
MATCH (k:Case)-[:INVOLVES]->(s) WHERE k.name CONTAINS 'Hoàng Nato' RETURN k.name, s.name
```

```text
{'k.name': 'Vụ bắt giang hồ Hoàng Nato và các đường dây ma túy tại TP.HCM', 's.name': 'Ketamine'}
{'k.name': 'Vụ triệt phá 8 đường dây ma túy liên quan đến ‘Hoàng Nato’ tại TP.HCM', 's.name': 'etomidate'}
{'k.name': 'Vụ tàng trữ và sử dụng pod chill chứa ma túy của 'Hoàng Nato' và TikToker Phannhibeauty tại TP.HCM', 's.name': 'etomidate'}
```

- **Nguyên nhân:** Ở KG-3, chúng ta lấy tất cả các Clause có `MENTIONS` một Substance mà Case `INVOLVES`. Trong luật có thể không có MENTIONS "etomidate" do chưa được chuẩn hóa, hoặc có quy định cụ thể mức khối lượng cho "Ketamine" nhưng Ontology hiện tại không lọc được (chỉ cần có INVOLVES và MENTIONS là match).
- **Đề xuất sửa:** Chuẩn hóa các tên chất ma túy mới/lóng (như etomidate) vào danh sách `SUBSTANCES` để sinh MENTIONS. Đặc biệt, bắt buộc thiết kế bổ sung thuộc tính `amount` (ngưỡng khối lượng) hoặc `threshold` vào `Clause` và đối chiếu với `amount` từ `Case` khi query ở KG-3 để lọc đúng khoản.

## 4. Kết luận (5 điểm)

Khi nào nên dùng KG, khi nào Flat RAG là đủ? Dẫn số liệu ở mục 1–2.
> - **Nên dùng KG khi:** Cần xử lý các câu hỏi tổng hợp/thống kê nhiều tài liệu (như Q6) hoặc liên kết thông tin giữa các thực thể có cấu trúc nằm ở các nguồn tri thức khác nhau (cross-kb như Q3, Q5). Số liệu benchmark cho thấy GraphRAG đạt recall tuyệt đối (1.0) so với Flat RAG (0.0 đến 0.40) ở các loại câu hỏi phức tạp này.
> - **Flat RAG đủ dùng khi:** Câu hỏi đơn giản chỉ truy xuất thông tin cụ thể (single-hop) nằm trọn trong 1 đoạn văn (Q1, Q2). Dùng Flat RAG sẽ tiết kiệm chi phí cực lớn khi lượng token input chỉ là 696 so với 5576 tokens của GraphRAG, giúp trả lời nhanh và cực rẻ mà vẫn đảm bảo độ chính xác.

## 5. Tự kiểm (5 điểm)

```text
$ pytest tests/ -q
................................................ [100%]
48 passed in 0.19s

$ python bench_kg.py --check
[OK] Dữ liệu: 18 điều luật, 20 bài báo
[OK] KG-1 link_entity
[OK] Neo4j kết nối được
[provider] chat = gemini:gemini-3.5-flash-lite | embedding = gemini:gemini-embedding-001
[OK] KG-2 build_graph: 148 node / 294 cạnh, đường xuyên 2 KB dài 2 cạnh
[OK] KG-3 context: 23 dữ kiện, có Điều 251
[OK] KG-4 GraphRAGAgent.answer
[OK] Chi phí check: 1 lần gọi LLM, $0.00000. Graph nhỏ (luật + 1 bài) vẫn còn trong Neo4j để bạn xem; chạy --judge để dựng graph đầy đủ.
```

Ảnh Neo4j: `report/img/kg_count.png`, `report/img/kg_cross_kb.png`, `report/img/kg_my_case.png`.
Người đã chọn cho `kg_my_case.png`: Cái Quang Huy

## Vấn đề gặp phải (không tính điểm)

Lỗi chưa giải quyết được: lệnh đã chạy, toàn bộ thông báo lỗi, những gì đã thử.
> - **Vấn đề RateLimit 429**: Bị lỗi khi dựng Knowledge Graph vì provider Gemini (gemini-3.5-flash-lite) giới hạn 15 RPM. **Khắc phục**: Đã thêm `time.sleep(4.5)` vào hàm `chat()` và `time.sleep(0.7)` vào hàm `embed()` trong `src/llm.py` để giảm tốc độ gửi request, qua đó vượt qua Rate Limit và hoàn tất benchmark thành công.

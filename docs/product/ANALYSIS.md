Tôi sẽ đánh giá theo góc “có thể build tool local thật hay không”, không chỉ lý thuyết. Trọng tâm là: đạt 100% MC/DC cho một file C, giới hạn 16GB RAM CPU, và mức “triệt để” có khả thi không.

Thought for 1m 32s

Kết luận quan trọng: khả thi nếu file .c là logic tương đối thuần, có thể compile độc lập, input hữu hạn/bounded, không phụ thuộc nhiều hardware/OS/concurrency. Nhưng không thể đảm bảo giải triệt để cho mọi file C bất kỳ để tự động sinh testcase đạt MC/DC = 100%. Đây nên được xem là bài toán hybrid test-generation + coverage-closing, không phải bài toán “đưa file C vào AI rồi sinh test chắc chắn đúng”.

1. Vì sao khả thi một phần?

MC/DC yêu cầu mỗi condition trong một decision phải được chứng minh là có thể độc lập làm thay đổi kết quả decision; tức là không chỉ chạy qua nhánh true/false mà còn phải tạo được các “independence pairs”.

Hiện có tool local hỗ trợ phần đo/kiểm chứng coverage:

Nhóm tool	Vai trò
Clang/LLVM coverage	Compile với coverage, đo report, có flag -fcoverage-mcdc trong source-based coverage.
llvm-cov / llvm-profdata	Tạo report từ binary instrumented và profile runtime.
GNATcoverage	Hỗ trợ C source coverage gồm statement, decision và MC/DC.
CBMC	Symbolic/bounded model checking cho C/C++; hữu ích để tìm input thỏa điều kiện, nhưng bị ràng buộc bởi loop unwinding/bounds.
KLEE	Symbolic execution có thể sinh test coverage cao, nhưng không phải đảm bảo 100% cho mọi chương trình thực tế. Paper KLEE báo line coverage cao, có tool đạt 100%, nhưng không phải tất cả; trung bình trên Coreutils vẫn là khoảng 90% per tool.

Với 16GB RAM CPU, nếu file nhỏ hoặc vừa, đặc biệt kiểu embedded C pure logic, khả năng chạy local là tốt. Không nhất thiết cần model AI lớn. AI nên hỗ trợ tạo harness/stub và phân tích gap, còn phần chứng minh coverage nên dựa vào compiler/tool deterministic. Đây cũng đúng với nguyên tắc “reliability beats intelligence” và hệ thống hybrid: dùng rules/tools/evaluation thay vì tin vào model tự đánh giá.

2. Phần khó thật sự không nằm ở MC/DC table

Với một expression như:

if ((a > 0 && b < 10) || flag)

tạo bảng boolean để cover MC/DC không quá khó.

Cái khó là: làm sao tìm được input concrete của function để ép từng condition nhận giá trị mong muốn, trong khi code thật có thể có:

if (sensor_ready() && ptr != NULL && arr[i] > limit && state->mode == ACTIVE)

Ở đây testcase không chỉ là {true,false}. Bạn phải setup được sensor_ready, ptr, arr, i, limit, state, global state, mock hardware, memory layout, compile flags, macro, include path, v.v.

Nói cách khác:

MC/DC target vector
→ path constraint
→ concrete input
→ harness setup
→ executable test
→ coverage report confirms it

Bước “path constraint → concrete input” là phần dễ nổ độ phức tạp nhất.

3. Những trường hợp 16GB RAM CPU có thể chạy ổn
Loại file C	Khả thi local 16GB?	Nhận định
Pure function, input primitive, ít pointer	Cao	Có thể brute-force + symbolic + coverage loop
Embedded logic, enum/state machine, ít loop	Cao-vừa	Cần harness tốt và bounds rõ
Nhiều macro/include nhưng compile được	Vừa	Cần build context/compile_commands.json
Nhiều pointer, struct sâu, dynamic memory	Vừa-thấp	Symbolic execution dễ nặng
Loop không bound, recursion, large array	Thấp	CBMC/KLEE dễ path explosion
Hardware register, volatile, interrupt, RTOS	Thấp nếu không mock	Cần environment model
File chỉ là một phần của project lớn	Thấp nếu thiếu dependency	Cần full build context/stub
4. Rủi ro chính
Rủi ro 1: File .c không compile độc lập

Một file C thực tế thường phụ thuộc .h, macro, typedef, global variable, build flag, target compiler, packing/alignment, conditional compilation. Nếu thiếu compile context, tool phân tích có thể hiểu sai code. Space ROS MC/DC checker cũng cho thấy front-end phải preprocess bằng Clang, walk AST, build BDD; lỗi include path là vấn đề thực tế khi chạy checker.

Rủi ro 2: 100% MC/DC có thể bất khả thi vì code unreachable

Nếu có dead code, defensive code không thể kích hoạt, condition bị constant-fold, hoặc state không thể đạt được từ public API, thì 100% theo tool có thể không đạt bằng testcase hợp lệ. Lúc đó hướng đúng không phải “cố sinh test bẩn”, mà là phân loại:

Gap	Cách xử lý đúng
Reachable nhưng chưa có input	Sinh thêm testcase
Unreachable do logic thật	Ghi justification/exclusion
Defensive code	Cần requirement hoặc test hook
Dead code	Refactor/remove hoặc mark excluded
Tool limitation	Đổi tool hoặc rewrite expression có kiểm soát
Rủi ro 3: Strongly-coupled conditions

Ví dụ:

if ((x > 3 && y > 2) || (x > 3 && y < 10))

Condition x > 3 xuất hiện nhiều lần. Một số toolchain yêu cầu rewrite expression để đạt full MC/DC đúng nghĩa. TI Arm Clang documentation nêu rõ strongly-coupled conditions, nested boolean expressions, constant conditions và short-circuit semantics là các điểm có thể ảnh hưởng đến MC/DC.

Rủi ro 4: Path explosion

Symbolic execution hoạt động bằng cách chạy chương trình với input symbolic, mỗi branch tạo path condition, rồi solver tìm concrete input cho path đó. Nhưng số path có thể tăng rất nhanh khi có nhiều branch, loop, array, pointer, function call. 16GB RAM CPU đủ cho nhiều file nhỏ/vừa, nhưng không đủ để “explore hết” code phức tạp.

Rủi ro 5: Coverage score không đồng nghĩa test tốt

MC/DC = 100% chỉ chứng minh structural coverage. Nó không đảm bảo assertion đúng, requirement đúng, output đúng, bug được phát hiện. KLEE paper cũng lưu ý generated tests có coverage cao nhưng chủ yếu kiểm tra low-level errors/asserts; developer tests thường validate output theo expected behavior.

5. Có giải quyết triệt để được không?

Với nghĩa mọi file C bất kỳ → tự động sinh testcase → MC/DC 100%, câu trả lời là không.

Lý do:

C có pointer, UB, macro, conditional compile, hardware dependency, concurrency, volatile, function pointer.
Reachability của path trong chương trình tổng quát là bài toán rất khó, nhiều trường hợp không thể quyết định hoàn toàn trong thực tế.
Tool symbolic/model checking đều cần bounds: loop bound, array bound, input domain, environment model.
Một số coverage gap không nên “giải bằng testcase” mà phải giải bằng requirement, exclusion hoặc refactor.

Nhưng với nghĩa một pipeline local có thể tự động sinh rất nhiều testcase, chạy coverage, đóng gap dần, và đạt 100% cho nhiều file C trong phạm vi kiểm soát, thì có thể build được.

6. Kiến trúc tôi khuyến nghị

Không nên dùng “LLM local generate test trực tiếp”. Nên dùng pipeline này:

.c + .h + compile_commands.json
→ Clang AST parse
→ Extract decisions/conditions
→ Generate MC/DC target vectors
→ Build harness + stubs
→ CBMC/KLEE/fuzzer tìm concrete inputs
→ Compile test runner with -fcoverage-mcdc
→ Run tests
→ llvm-cov/GNATcoverage report
→ Gap analyzer
→ Iterate until 100% or classify unachievable
Vai trò từng phần
Component	Trách nhiệm
Clang AST parser	Lấy decision/condition chính xác
BDD/truth-vector generator	Sinh MC/DC target vectors
Harness generator	Tạo wrapper test cho function
Stub/mock engine	Mock external calls, globals, hardware
CBMC/KLEE	Tìm input thỏa path constraint
Fuzzer	Bù cho symbolic execution khi solver khó
Coverage oracle	Clang/llvm-cov hoặc GNATcoverage xác nhận score
Gap classifier	Reachable / unreachable / tool limitation / needs refactor
Local LLM nhỏ	Hỗ trợ viết harness/stub, không làm oracle
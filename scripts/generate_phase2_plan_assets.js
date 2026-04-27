const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT_DIR = "/tmp/jwbot_phase2_plan";
const BASENAME = "公司JW-Bot人工智能办公系统二期深度开发计划";

fs.mkdirSync(OUT_DIR, { recursive: true });

const htmlPath = path.join(OUT_DIR, `${BASENAME}.html`);
const pptPath = path.join(OUT_DIR, `${BASENAME}.pptx`);

const C = {
  ink: "172033",
  muted: "667085",
  line: "D7DEE9",
  bg: "F6F8FB",
  white: "FFFFFF",
  navy: "0F172A",
  blue: "2563EB",
  cyan: "0891B2",
  green: "0F766E",
  amber: "B45309",
  red: "B91C1C",
  slate: "334155",
  paleBlue: "EFF6FF",
  paleCyan: "ECFEFF",
  paleGreen: "F0FDFA",
  paleAmber: "FFFBEB",
};

const cards = [
  {
    tag: "核心结论",
    title: "二期不是让 Hermes 直接接管任务，而是让 Harness 判断何时升级",
    body: [
      "一期链路：员工通过 QQ/飞书对话进入 AstrBot，Router/Harness 识别并管理任务，AstrBot 的 LLM 先通过对话方式产出结果。",
      "二期链路：如果员工满意，任务在 AstrBot + Harness 里闭环；如果员工不满意、结果太泛或任务复杂度上升，Harness 才调度 Hermes 深度执行。",
      "Hermes 不自己判定是否升级。升级判断必须交给 Harness，因为 Harness 才掌握员工反馈、任务上下文、历史结果和公司业务规则。",
    ],
  },
  {
    tag: "AstrBot",
    title: "AstrBot 是公司智能办公系统的前台和工作台",
    body: [
      "它负责接收 QQ/飞书消息，识别员工身份，管理不同员工和不同 IM 频道的会话隔离。",
      "它能做即时对话、人格配置、新员工引导、插件调用、任务入口、结果推送和后台管理。",
      "它适合做员工每天真正接触的界面，因为员工不需要学习新工具，只在 QQ/飞书里提需求和收结果。",
      "它的短板是深度执行能力有限，复杂任务不能只靠一次普通 LLM 回复解决。",
    ],
  },
  {
    tag: "Hermes",
    title: "Hermes 是后台执行引擎，不是员工聊天入口",
    body: [
      "它擅长联网搜索、多步骤推理、工具调用、文件处理、浏览器自动化和复杂任务执行。",
      "它适合处理 AstrBot 初稿无法满足的深度任务，比如竞品研究、资料整合、复杂方案补强。",
      "它的短板是天然偏单任务执行，不适合直接面对多员工、多频道、多会话的企业场景。",
      "因此它需要 AstrBot + Router + Harness 作为前台分流层和任务管理层。",
    ],
  },
  {
    tag: "Router",
    title: "Router 是智能分流器，决定每句话走哪条路",
    body: [
      "员工一句话进来，Router 判断它是普通对话、技能调用，还是正式工作任务。",
      "开发 Router 的原因是：没有分流，所有消息都会混在一起，系统不知道什么时候聊天、什么时候建任务、什么时候调用工具。",
      "现在 Router 已支持规则匹配 + LLM 二次判断，能识别营销策划、内容交付、项目跟进、审批请求、PPT、搜索等场景。",
      "后期对 Router 的更高期待：识别员工真实意图、上下文中的隐含需求、升级信号、风险信号，并把多用户任务准确送入 Harness。",
    ],
  },
  {
    tag: "Harness",
    title: "Harness 是整个公司系统最重要的任务大脑",
    body: [
      "Harness 不是普通任务列表，它是连接员工需求、AstrBot 初稿、员工反馈、Hermes 深度执行和长期记忆的中枢。",
      "它记录谁提出需求、任务是什么、当前做到哪一步、员工是否满意、结果有没有交付、哪些经验要沉淀。",
      "二期最关键的开发就是 Harness：满意度判定、升级调度、任务状态机、记忆检索、知识库上下文和多轮任务管理都要围绕它做。",
      "如果 Harness 做弱了，系统就只是聊天机器人；Harness 做强了，系统才会变成公司级智能办公系统。",
    ],
  },
  {
    tag: "一期现状",
    title: "一期已经能跑通前台链路，但还不是真正的深度办公系统",
    body: [
      "员工可以通过 QQ/飞书与 AstrBot 对话，系统能进行人格引导、任务识别、初步方案生成和回复。",
      "当前主要价值是前台接待和初稿产出，已经具备员工测试基础。",
      "当前主要问题是方案容易泛、知识库没有充分参与、短期/长期记忆没有真正反哺生成、复杂任务没有稳定升级到 Hermes。",
    ],
  },
  {
    tag: "二期主线",
    title: "二期要做满意度驱动的双系统协作",
    body: [
      "第一步：AstrBot 通过 QQ/飞书继续与员工对话，Harness 识别并跟踪任务。",
      "第二步：AstrBot LLM 根据员工补充信息先产出方案或阶段结果。",
      "第三步：Harness 持续观察员工反馈。如果员工满意，任务闭环；如果员工不满意，Harness 将任务派发给 Hermes。",
      "第四步：Hermes 深度执行后回传结果，AstrBot 再通过 QQ/飞书送达员工，Harness 完成任务并沉淀记忆。",
    ],
  },
  {
    tag: "多任务设想",
    title: "AstrBot + Router + Harness 是 Hermes 多任务化的前提",
    body: [
      "Hermes 本身更像一个专注的单任务执行者，不天然适合同时面对多个员工的多条任务线。",
      "公司的设想是用 AstrBot 的多聊天频道、多用户会话，加上 Router 分流和 Harness 任务队列，把多个员工的任务有序派发给 Hermes。",
      "这件事理论上可行，但不是简单配置，需要二期或后续专门做任务队列、并发控制、状态回传和失败重试。",
    ],
  },
  {
    tag: "知识与记忆",
    title: "解决方案太泛，关键是知识库和记忆参与任务",
    body: [
      "知识库提供品牌规范、历史案例、产品资料、客群画像和文案风格，让系统输出有公司依据。",
      "短期记忆记录同一任务的上下文，避免员工反复解释背景。",
      "长期记忆沉淀员工偏好、历史任务结果和有效经验，让系统越用越懂公司。",
      "这些能力最终都要由 Harness 统一管理，在合适时间注入给 AstrBot LLM 或 Hermes。",
    ],
  },
  {
    tag: "开发计划",
    title: "二期开发优先级必须围绕 Harness 展开",
    body: [
      "P0：Harness 满意度检测、升级调度、任务状态机和 Hermes 回传闭环。",
      "P0：知识库接入任务链路，让 AstrBot 初稿和 Hermes 深度执行都有公司资料可用。",
      "P1：Router 口语词库和隐含意图识别，提升员工自然表达下的分流准确率。",
      "P1：短期/长期记忆检索注入，形成越用越聪明的系统。",
      "P2：Hermes 多任务队列与并发调度，作为后续独立架构升级。",
    ],
  },
];

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function buildHtml() {
  const sections = cards
    .map(
      (card, idx) => `
      <section class="card">
        <div class="num">${String(idx + 1).padStart(2, "0")}</div>
        <div>
          <p class="tag">${esc(card.tag)}</p>
          <h2>${esc(card.title)}</h2>
          <ul>${card.body.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
        </div>
      </section>`
    )
    .join("\n");

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>公司 JW-Bot 人工智能办公系统二期深度开发计划</title>
  <style>
    :root {
      --ink:#172033; --muted:#667085; --line:#d7dee9; --bg:#f6f8fb; --white:#fff;
      --navy:#0f172a; --blue:#2563eb; --cyan:#0891b2; --green:#0f766e; --amber:#b45309; --red:#b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.68;
    }
    .hero {
      min-height: 70vh;
      padding: 56px clamp(22px, 6vw, 88px);
      color: white;
      display: flex;
      flex-direction: column;
      justify-content: center;
      background:
        linear-gradient(rgba(15,23,42,.72), rgba(15,23,42,.78)),
        url("https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=1800&q=85") center/cover;
    }
    .eyebrow {
      width: fit-content;
      border: 1px solid rgba(255,255,255,.35);
      background: rgba(255,255,255,.12);
      padding: 6px 12px;
      margin-bottom: 24px;
      font-size: 14px;
    }
    h1 {
      max-width: 1040px;
      margin: 0;
      font-size: clamp(36px, 6vw, 72px);
      line-height: 1.08;
      letter-spacing: 0;
    }
    .hero p {
      max-width: 920px;
      margin: 24px 0 0;
      font-size: clamp(17px, 2vw, 22px);
      color: rgba(255,255,255,.9);
    }
    main { padding: 44px clamp(18px, 4vw, 64px) 72px; }
    .metrics {
      max-width: 1180px;
      margin: -86px auto 36px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      position: relative;
    }
    .metric, .flow, .card, .table-block {
      background: var(--white);
      border: 1px solid var(--line);
    }
    .metric { padding: 20px; min-height: 130px; }
    .metric b { display: block; color: var(--blue); font-size: 28px; }
    .metric span { color: var(--muted); display: block; margin-top: 8px; }
    .flow {
      max-width: 1180px;
      margin: 0 auto 20px;
      padding: 28px;
    }
    h2 { margin: 0 0 14px; font-size: clamp(24px, 3vw, 34px); line-height: 1.25; letter-spacing: 0; }
    .tag { margin: 0 0 8px; color: var(--cyan); font-weight: 700; }
    .flow-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
      margin-top: 22px;
    }
    .step {
      padding: 15px 12px;
      min-height: 118px;
      border: 1px solid var(--line);
      background: #fbfcfe;
    }
    .step b { display: block; color: var(--green); margin-bottom: 8px; }
    .step p { margin: 0; color: var(--muted); font-size: 14px; }
    .split {
      max-width: 1180px;
      margin: 20px auto;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    .table-block { padding: 24px; }
    table { width: 100%; border-collapse: collapse; font-size: 15px; }
    th, td { border-bottom: 1px solid var(--line); padding: 12px 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 700; }
    .card {
      max-width: 1180px;
      margin: 16px auto;
      padding: 28px;
      display: grid;
      grid-template-columns: 72px minmax(0, 1fr);
      gap: 22px;
    }
    .num {
      width: 54px;
      height: 54px;
      border: 1px solid var(--line);
      display: grid;
      place-items: center;
      color: var(--blue);
      font-weight: 800;
    }
    ul { margin: 0; padding-left: 20px; }
    li + li { margin-top: 8px; }
    .timeline {
      max-width: 1180px;
      margin: 28px auto 0;
      padding: 30px;
      background: var(--navy);
      color: white;
    }
    .timeline h2 { color: white; }
    .timeline-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 20px; }
    .phase { border: 1px solid rgba(255,255,255,.22); padding: 16px; min-height: 145px; }
    .phase b { color: #67e8f9; }
    .phase p { color: rgba(255,255,255,.78); margin: 10px 0 0; }
    footer { max-width: 1180px; margin: 28px auto 0; color: var(--muted); font-size: 14px; }
    @media (max-width: 900px) {
      .metrics, .flow-grid, .timeline-grid, .split { grid-template-columns: 1fr 1fr; }
      .card { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .metrics, .flow-grid, .timeline-grid, .split { grid-template-columns: 1fr; }
      .hero { min-height: 64vh; }
    }
    @media print {
      .hero { min-height: auto; }
      .metrics { margin-top: 24px; }
      .card, .flow, .metric, .table-block, .timeline { break-inside: avoid; }
    }
  </style>
</head>
<body>
  <header class="hero">
    <div class="eyebrow">巅池文化传媒公司内部技术开发文档 · 2026-04-24</div>
    <h1>公司 JW-Bot 人工智能办公系统二期深度开发计划</h1>
    <p>重新定义正确链路：AstrBot 先承接员工对话并由 Harness 调度 AstrBot LLM 产出结果；只有在员工不满意、任务复杂或需要深度执行时，Harness 才升级派发给 Hermes。</p>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><b>AstrBot</b><span>员工入口、前台工作台、即时对话和结果推送</span></div>
      <div class="metric"><b>Router</b><span>智能分流器，判断聊天、技能还是任务</span></div>
      <div class="metric"><b>Harness</b><span>最核心任务大脑，负责满意度和升级判定</span></div>
      <div class="metric"><b>Hermes</b><span>后台深度执行引擎，处理升级任务</span></div>
    </section>

    <section class="flow">
      <p class="tag">正确系统链路</p>
      <h2>二期不是“直接给 Hermes”，而是“先 AstrBot，后 Harness 判定升级”</h2>
      <div class="flow-grid">
        <div class="step"><b>员工</b><p>通过 QQ/飞书提出需求和补充信息。</p></div>
        <div class="step"><b>AstrBot</b><p>接收消息，维持员工对话。</p></div>
        <div class="step"><b>Router</b><p>分流到对话、技能或任务。</p></div>
        <div class="step"><b>Harness</b><p>建立任务并调度 AstrBot LLM。</p></div>
        <div class="step"><b>员工反馈</b><p>满意则闭环，不满意则进入升级调度。</p></div>
        <div class="step"><b>Hermes</b><p>只处理被升级的复杂执行任务。</p></div>
      </div>
    </section>

    <section class="split">
      <div class="table-block">
        <p class="tag">一期实际链路</p>
        <h2>当前能交付什么</h2>
        <table>
          <tr><th>环节</th><th>说明</th></tr>
          <tr><td>入口</td><td>员工通过 QQ/飞书和 AstrBot 对话。</td></tr>
          <tr><td>任务理解</td><td>Router/Harness 识别工作任务并建立记录。</td></tr>
          <tr><td>结果产出</td><td>AstrBot LLM 根据对话话术和员工补充生成初步结果。</td></tr>
          <tr><td>局限</td><td>复杂任务、联网搜索、深度研究和长期记忆使用还不够。</td></tr>
        </table>
      </div>
      <div class="table-block">
        <p class="tag">二期目标链路</p>
        <h2>下一步要升级什么</h2>
        <table>
          <tr><th>判断条件</th><th>动作</th></tr>
          <tr><td>员工满意</td><td>Harness 完成任务，沉淀结果和记忆。</td></tr>
          <tr><td>员工不满意</td><td>Harness 判定升级，把任务交给 Hermes 深度执行。</td></tr>
          <tr><td>任务复杂</td><td>需要搜索、工具、多步骤推理时升级 Hermes。</td></tr>
          <tr><td>多用户</td><td>AstrBot/Router/Harness 负责分流，Hermes 后台排队执行。</td></tr>
        </table>
      </div>
    </section>

    ${sections}

    <section class="timeline">
      <h2>建议开发节奏</h2>
      <div class="timeline-grid">
        <div class="phase"><b>第 1-2 周</b><p>重点开发 Harness 满意度判定、任务状态机、升级调度。</p></div>
        <div class="phase"><b>第 3 周</b><p>接入知识库，让 AstrBot 初稿和 Hermes 深度执行都有公司资料。</p></div>
        <div class="phase"><b>第 4-5 周</b><p>激活短期/长期记忆，开展 3-5 名员工小范围测试。</p></div>
        <div class="phase"><b>第 6-8 周</b><p>完善 Router 词库、稳定性、运维和员工反馈闭环。</p></div>
      </div>
    </section>

    <footer>
      巅池文化传媒公司内部技术开发文档
    </footer>
  </main>
</body>
</html>`;
}

function title(pptx, slide, text, sub) {
  slide.addText(text, {
    x: 0.65,
    y: 0.58,
    w: 11.8,
    h: 0.58,
    fontFace: "Arial",
    fontSize: 25,
    bold: true,
    color: C.ink,
    margin: 0,
    fit: "shrink",
  });
  if (sub) {
    slide.addText(sub, {
      x: 0.66,
      y: 1.24,
      w: 11.2,
      h: 0.34,
      fontFace: "Arial",
      fontSize: 11.5,
      color: C.muted,
      margin: 0,
      fit: "shrink",
    });
  }
  slide.addShape(pptx.ShapeType.line, {
    x: 0.65,
    y: 1.78,
    w: 12,
    h: 0,
    line: { color: C.line, width: 1 },
  });
}

function bullets(slide, list, x, y, w, h, size = 14) {
  slide.addText(
    list.map((item) => ({ text: item, options: { bullet: { type: "bullet" } } })),
    {
      x,
      y,
      w,
      h,
      fontFace: "Arial",
      fontSize: size,
      color: C.ink,
      fit: "shrink",
      margin: 0.04,
      paraSpaceAfterPt: 7,
      breakLine: false,
    }
  );
}

function smallBox(pptx, slide, label, detail, x, y, w, h, fill, accent) {
  slide.addShape(pptx.ShapeType.rect, {
    x,
    y,
    w,
    h,
    fill: { color: fill },
    line: { color: C.line, width: 1 },
  });
  slide.addText(label, {
    x: x + 0.12,
    y: y + 0.18,
    w: w - 0.24,
    h: 0.25,
    fontSize: 15,
    bold: true,
    color: accent,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
  slide.addText(detail, {
    x: x + 0.15,
    y: y + 0.55,
    w: w - 0.3,
    h: h - 0.7,
    fontSize: 10.5,
    color: C.muted,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
}

async function buildPpt() {
  const pptx = new pptxgen();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "巅池文化传媒";
  pptx.subject = "JW-Bot 二期深度开发计划";
  pptx.title = "公司JW-Bot人工智能办公系统二期深度开发计划";
  pptx.company = "JW-Bot";
  pptx.lang = "zh-CN";
  pptx.theme = { headFontFace: "Arial", bodyFontFace: "Arial", lang: "zh-CN" };
  pptx.defineLayout({ name: "LAYOUT_WIDE", width: 13.333, height: 7.5 });

  let s = pptx.addSlide();
  s.background = { color: C.navy };
  s.addText("巅池文化传媒公司内部技术开发文档 · 2026-04-24", {
    x: 0.72,
    y: 0.72,
    w: 4.2,
    h: 0.25,
    fontSize: 12,
    color: "B8C7DD",
    margin: 0,
  });
  s.addText("公司 JW-Bot\n人工智能办公系统\n二期深度开发计划", {
    x: 0.72,
    y: 1.25,
    w: 7.3,
    h: 2.5,
    fontSize: 34,
    bold: true,
    color: C.white,
    margin: 0,
    fit: "shrink",
  });
  s.addText("正确链路：AstrBot 先通过 QQ/飞书对话与 Harness 调度产出结果；只有员工不满意或任务复杂时，Harness 才升级给 Hermes。", {
    x: 0.75,
    y: 4.1,
    w: 7.9,
    h: 0.72,
    fontSize: 16,
    color: "E2E8F0",
    margin: 0,
    fit: "shrink",
  });
  s.addShape(pptx.ShapeType.rect, { x: 9.05, y: 0.9, w: 3.4, h: 5.7, fill: { color: "1E293B", transparency: 8 }, line: { color: "334155" } });
  s.addText("开发判断重点", { x: 9.35, y: 1.28, w: 2.65, h: 0.28, fontSize: 18, bold: true, color: C.white, margin: 0 });
  bullets(s, [
    "AstrBot 是员工入口和一期结果产出主体。",
    "Harness 是满意度判定和升级调度核心。",
    "Hermes 是后台深度执行引擎，只接收派发任务。",
    "Router 负责多频道、多用户、多任务的准确分流。",
  ], 9.38, 2.0, 2.55, 2.8, 13.5);

  s = pptx.addSlide();
  title(pptx, s, "正确系统链路：先 AstrBot，后 Harness 判断是否升级", "二期不是绕过 AstrBot，而是让两个系统各做最擅长的事。");
  const steps = [
    ["员工", "QQ/飞书提出需求"],
    ["AstrBot", "接收并维持对话"],
    ["Router", "判断对话/技能/任务"],
    ["Harness", "建任务并调度 AstrBot LLM"],
    ["员工反馈", "满意则闭环，不满意则升级"],
    ["Hermes", "后台深度执行并回传"],
  ];
  steps.forEach(([a, b], i) => {
    const x = 0.52 + i * 2.08;
    smallBox(pptx, s, a, b, x, 2.55, 1.58, 1.18, [C.paleBlue, C.paleCyan, C.paleGreen, C.paleAmber, "FEF2F2", "F8FAFC"][i], [C.blue, C.cyan, C.green, C.amber, C.red, C.slate][i]);
    if (i < steps.length - 1) {
      s.addShape(pptx.ShapeType.chevron, { x: x + 1.67, y: 2.9, w: 0.25, h: 0.3, fill: { color: C.blue }, line: { color: C.blue } });
    }
  });
  bullets(s, [
    "一期：AstrBot 通过 QQ 对话互动话术，让 Harness 理解任务并调度 AstrBot LLM 出结果。",
    "二期：Harness 根据员工上下文和反馈判断是否满意，不满意才把任务升级给 Hermes。",
    "历史上单独使用执行系统时可能存在自我升级机制；在公司系统中，升级判定权必须统一交给 Harness。",
  ], 1.0, 4.55, 11.0, 1.35, 15);

  s = pptx.addSlide();
  title(pptx, s, "AstrBot 是什么，它能做什么", "AstrBot 是员工真正接触的前台工作台。");
  smallBox(pptx, s, "定位", "公司智能办公系统前台、员工入口、IM 工作台", 0.85, 2.25, 3.5, 1.0, C.paleBlue, C.blue);
  smallBox(pptx, s, "能做什么", "QQ/飞书接入、人格配置、插件调用、任务入口、即时回复、结果推送", 4.9, 2.25, 3.5, 1.0, C.paleCyan, C.cyan);
  smallBox(pptx, s, "为什么重要", "员工不用学习新系统，直接在日常 IM 里完成办公需求", 8.95, 2.25, 3.5, 1.0, C.paleGreen, C.green);
  bullets(s, [
    "AstrBot 负责多员工、多频道、多会话的隔离和管理，这是 Hermes 原生不具备的。",
    "一期主要由 AstrBot LLM 通过对话承接任务结果，这是当前可交付链路。",
    "AstrBot 的短板是深度执行能力有限，所以二期需要接入 Hermes，但不能直接跳过 AstrBot。",
  ], 1.0, 4.2, 11.2, 1.55, 15);

  s = pptx.addSlide();
  title(pptx, s, "Hermes 是什么，它能做什么", "Hermes 是后台深度执行引擎，不是员工聊天入口。");
  smallBox(pptx, s, "擅长", "联网搜索、多步骤推理、工具调用、文件/浏览器自动化", 0.9, 2.25, 3.75, 1.18, C.paleGreen, C.green);
  smallBox(pptx, s, "适合处理", "AstrBot 初稿不能满足的竞品研究、资料整合、深度方案补强", 4.8, 2.25, 3.75, 1.18, C.paleAmber, C.amber);
  smallBox(pptx, s, "短板", "偏单任务执行，不适合直接面对多员工、多频道、多任务", 8.7, 2.25, 3.75, 1.18, "FEF2F2", C.red);
  bullets(s, [
    "Hermes 的价值不是替代 AstrBot，而是在 Harness 判断需要深度执行时接棒。",
    "单独使用执行系统时的自运行机制不适合公司多系统环境；放到公司系统里，必须由 Harness 统一判断。",
    "未来多任务能力要靠 AstrBot 多频道 + Router 分流 + Harness 队列，而不是靠 Hermes 自己硬扛。",
  ], 1.0, 4.35, 11.2, 1.55, 15);

  s = pptx.addSlide();
  title(pptx, s, "Router 为什么必须开发", "没有 Router，系统就不知道员工这句话该怎么处理。");
  smallBox(pptx, s, "普通对话", "解释说明、寒暄、轻问答", 1.0, 2.28, 2.25, 0.95, C.paleBlue, C.blue);
  smallBox(pptx, s, "技能调用", "PPT、图片、搜索、插件工具", 3.85, 2.28, 2.25, 0.95, C.paleCyan, C.cyan);
  smallBox(pptx, s, "工作任务", "营销策划、内容交付、项目跟进、审批", 6.7, 2.28, 2.25, 0.95, C.paleGreen, C.green);
  smallBox(pptx, s, "升级信号", "太泛了、重做、再深入一点", 9.55, 2.28, 2.25, 0.95, "FEF2F2", C.red);
  bullets(s, [
    "Router 的分流作用是把每条消息送到正确处理路径，避免所有需求都混成普通聊天。",
    "现在 Router 已支持规则匹配 + LLM 二次判断，二期要继续扩充口语词库和隐含意图识别。",
    "更高期待：识别员工是否在表达不满意、是否需要升级、是否存在审批/交付/跟进风险，并准确交给 Harness。",
  ], 1.0, 4.25, 11.2, 1.65, 15);

  s = pptx.addSlide();
  title(pptx, s, "Harness 是最最最重要的公司任务大脑", "二期开发的核心不只是接 Hermes，而是把 Harness 做强。");
  s.addShape(pptx.ShapeType.ellipse, { x: 5.25, y: 2.1, w: 2.75, h: 1.22, fill: { color: C.paleGreen }, line: { color: C.green, width: 1.2 } });
  s.addText("Harness\n任务大脑", { x: 5.55, y: 2.45, w: 2.15, h: 0.42, fontSize: 20, bold: true, color: C.green, align: "center", margin: 0, fit: "shrink" });
  const nodes = [
    ["员工需求", 0.8, 2.25, C.blue],
    ["AstrBot 初稿", 2.95, 4.5, C.cyan],
    ["员工反馈", 5.35, 5.35, C.amber],
    ["Hermes 升级", 8.0, 4.5, C.red],
    ["长期记忆", 10.3, 2.25, C.slate],
  ];
  nodes.forEach(([txt, x, y, color]) => smallBox(pptx, s, txt, "由 Harness 记录、判断、调度", x, y, 1.85, 0.78, C.white, color));
  bullets(s, [
    "Harness 记录任务全生命周期：谁提的、提了什么、做到了哪一步、结果如何、员工是否满意。",
    "Harness 决定是否升级 Hermes，而不是让 Hermes 自己判断。",
    "Harness 负责把有价值的结果沉淀为短期/长期记忆，让系统越用越懂公司。",
    "二期最关键开发：满意度判定、状态机、升级调度、知识库/记忆注入、多轮任务管理。",
  ], 0.95, 6.08, 11.6, 0.9, 12.2);

  s = pptx.addSlide();
  title(pptx, s, "一期现状与二期目标", "当前链路可测试，二期要补上深度执行和任务治理。");
  s.addText("一期", { x: 1.0, y: 2.18, w: 1.0, h: 0.3, fontSize: 20, bold: true, color: C.blue, margin: 0 });
  bullets(s, [
    "QQ/飞书进入 AstrBot。",
    "Router/Harness 识别任务。",
    "AstrBot LLM 通过对话产出初步结果。",
    "适合前台接待和初稿产出。",
  ], 1.05, 2.75, 4.7, 2.1, 14);
  s.addShape(pptx.ShapeType.line, { x: 6.55, y: 2.18, w: 0, h: 3.75, line: { color: C.line, width: 1 } });
  s.addText("二期", { x: 7.15, y: 2.18, w: 1.0, h: 0.3, fontSize: 20, bold: true, color: C.green, margin: 0 });
  bullets(s, [
    "Harness 识别满意/不满意。",
    "满意则闭环并沉淀记忆。",
    "不满意或复杂任务才升级 Hermes。",
    "Hermes 深度执行后回传 QQ/飞书。",
  ], 7.2, 2.75, 4.8, 2.1, 14);

  s = pptx.addSlide();
  title(pptx, s, "知识库、短期记忆、长期记忆必须围绕 Harness 使用", "解决“方案泛”的关键是让模型拥有公司资料和历史经验。");
  const memory = [
    ["知识库", "品牌规范、成功案例、产品资料、客群画像、文案风格", C.blue],
    ["短期记忆", "同一任务中的背景、约束、补充信息和员工反馈", C.cyan],
    ["长期记忆", "员工偏好、历史任务、有效方案和可复用经验", C.green],
  ];
  memory.forEach(([a, b, color], i) => smallBox(pptx, s, a, b, 0.9 + i * 4.05, 2.35, 3.35, 1.45, [C.paleBlue, C.paleCyan, C.paleGreen][i], color));
  bullets(s, [
    "这些不是独立摆设，而要由 Harness 在任务合适阶段注入给 AstrBot LLM 或 Hermes。",
    "如果知识库和记忆不进入任务链路，换更强模型也容易输出通用模板。",
    "公司需要尽早提供品牌规范、历史方案、产品资料和目标客群资料。",
  ], 1.0, 4.75, 11.0, 1.2, 15);

  s = pptx.addSlide();
  title(pptx, s, "Hermes 多任务化：方向正确，但需要重新整合开发", "你的判断是对的：AstrBot 是让 Hermes 服务多员工的关键分流层。");
  bullets(s, [
    "Hermes 本身偏单任务，适合专注完成一个复杂任务。",
    "公司场景是多员工、多频道、多任务，不能让 Hermes 直接面对所有聊天入口。",
    "可行思路：Router 识别任务 → Harness 建队列和状态 → Hermes 按任务执行 → AstrBot 回传结果。",
    "这需要专门开发任务队列、并发控制、超时重试、结果回传和状态展示，建议作为二期后段或独立三期项目。",
  ], 1.0, 2.2, 11.2, 2.2, 16);
  smallBox(pptx, s, "目标", "让单任务执行型 Hermes 通过 AstrBot/Harness 的分流和队列，服务多个员工。", 2.0, 5.05, 9.2, 0.95, C.paleAmber, C.amber);

  s = pptx.addSlide();
  title(pptx, s, "二期开发优先级", "先把 Harness 做强，再谈大规模多任务。");
  const rows = [
    ["P0", "Harness 满意度检测 + 升级调度", "决定是否派发 Hermes 的核心机制"],
    ["P0", "Hermes 回传 + Harness 任务闭环", "深度执行结果回到 QQ/飞书并沉淀任务"],
    ["P0", "知识库接入任务链路", "让 AstrBot 初稿和 Hermes 深度执行都有公司依据"],
    ["P1", "Router 口语与隐含意图识别", "让员工自然表达也能被准确分流"],
    ["P1", "短期/长期记忆注入", "让系统越用越懂员工和公司"],
    ["P2", "Hermes 多任务队列", "独立架构升级，需专项开发"],
  ];
  rows.forEach(([p, name, detail], i) => {
    const y = 2.03 + i * 0.66;
    s.addShape(pptx.ShapeType.rect, { x: 0.82, y, w: 11.7, h: 0.48, fill: { color: C.white }, line: { color: C.line } });
    const pc = p === "P0" ? C.red : p === "P1" ? C.blue : C.slate;
    s.addShape(pptx.ShapeType.rect, { x: 0.82, y, w: 0.7, h: 0.48, fill: { color: pc }, line: { color: pc } });
    s.addText(p, { x: 0.94, y: y + 0.15, w: 0.46, h: 0.14, fontSize: 9.5, bold: true, color: C.white, align: "center", margin: 0 });
    s.addText(name, { x: 1.75, y: y + 0.13, w: 4.4, h: 0.17, fontSize: 13.5, bold: true, color: C.ink, margin: 0, fit: "shrink" });
    s.addText(detail, { x: 6.2, y: y + 0.13, w: 5.7, h: 0.17, fontSize: 12, color: C.muted, margin: 0, fit: "shrink" });
  });

  s = pptx.addSlide();
  title(pptx, s, "公司需要配合什么", "业务资料和真实反馈决定二期效果。");
  smallBox(pptx, s, "市场 / 品牌", "品牌规范、历史案例、产品资料、客群画像、文案风格", 0.95, 2.35, 3.55, 1.28, C.paleBlue, C.blue);
  smallBox(pptx, s, "测试员工", "3-5 人真实试用，直接反馈满意、不满意、哪里太泛", 4.9, 2.35, 3.55, 1.28, C.paleGreen, C.green);
  smallBox(pptx, s, "IT / 运维", "Mac mini、路由器、QQ/飞书 API、LLM 网络稳定", 8.85, 2.35, 3.55, 1.28, C.paleAmber, C.amber);
  bullets(s, [
    "员工不需要学习新软件，只需要在 QQ/飞书里用真实工作需求测试。",
    "公司资料越真实、越完整，系统输出越不容易泛。",
    "反馈不要客气：直接说“太泛了、重做、再具体点”，这些就是 Harness 二期要识别的升级判断信号。",
  ], 1.0, 4.65, 11.2, 1.3, 15);

  s = pptx.addSlide();
  s.background = { color: C.navy };
  s.addText("建议立项判断", { x: 0.82, y: 0.8, w: 3.2, h: 0.4, fontSize: 25, bold: true, color: C.white, margin: 0 });
  s.addText("二期的核心不是“接上 Hermes”这么简单，而是把 Harness 做成公司智能办公系统的任务大脑。", {
    x: 1.0,
    y: 1.82,
    w: 11.2,
    h: 0.95,
    fontSize: 28,
    bold: true,
    color: C.white,
    align: "center",
    margin: 0,
    fit: "shrink",
  });
  bullets(s, [
    "AstrBot 负责员工入口和一期结果产出。",
    "Harness 负责判断满意度、调度升级、管理任务和沉淀记忆。",
    "Hermes 负责被升级后的深度执行。",
    "Router 负责把多员工、多频道、多类型消息准确分流。",
  ], 1.35, 3.8, 10.4, 1.65, 17);
  s.addText("做强这四层，JW-Bot 才会从机器人变成公司内部智能办公系统。", {
    x: 1.2,
    y: 6.35,
    w: 10.9,
    h: 0.26,
    fontSize: 16,
    bold: true,
    color: "67E8F9",
    align: "center",
    margin: 0,
  });

  await pptx.writeFile({ fileName: pptPath });
}

fs.writeFileSync(htmlPath, buildHtml(), "utf8");
buildPpt().then(() => {
  console.log(htmlPath);
  console.log(pptPath);
});

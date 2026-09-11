import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "/Users/tjhouse/Projects/HouseholdOS";
const SKILL_DIR = "/Users/tjhouse/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const TMP_DIR = path.join(workspaceDir, "tmp/presentations");
const FINAL_PPTX = path.join(workspaceDir, "output/pptx/HouseholdOS_Final_Capstone_Presentation_With_Live_Demo.pptx");
await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const font = resolvePresentationFont();
const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const C = { ink: "#172B25", green: "#176B57", mint: "#DCEDE6", lime: "#B9DB7C", coral: "#E97962", cream: "#F7F5EF", white: "#FFFFFF", gray: "#61706A", line: "#BDD0C7" };

function box(slide, x, y, w, h, fill=C.white, radius="roundRect") {
  return slide.shapes.add({ geometry: radius, position:{left:x,top:y,width:w,height:h}, fill, line:{fill:C.line,width:1} });
}
function textBox(slide, text, x, y, w, h, size=24, color=C.ink, bold=false, align="left") {
  const s=slide.shapes.add({geometry:"textbox",position:{left:x,top:y,width:w,height:h},fill:"none",line:{fill:"none",width:0}});
  s.text=text; s.text.style={typeface:font,fontSize:size,color,bold,autoFit:"shrinkText",textAlign:align,verticalAlignment:"middle"}; return s;
}
function title(slide, t, n) {
  slide.background.fill=C.cream;
  textBox(slide,t,70,42,1030,62,35,C.ink,true);
  textBox(slide,String(n).padStart(2,"0"),1170,50,50,34,16,C.green,true,"right");
  const line=slide.shapes.add({geometry:"rect",position:{left:70,top:116,width:1140,height:4},fill:C.green,line:{fill:C.green,width:0}});
  return line;
}
function note(slide, text){ slide.speakerNotes.textFrame.setText(text); }
function label(slide, t, x,y,w, color=C.green){ textBox(slide,t.toUpperCase(),x,y,w,24,14,color,true); }

// 1
{
 const s=p.slides.add(); s.background.fill=C.cream;
 textBox(s,"HouseholdOS",74,165,750,85,58,C.ink,true);
 textBox(s,"An approval-gated AI Chief of Staff",78,255,720,42,27,C.green,false);
 textBox(s,"Family operations and church ministry in one reviewable workflow",78,316,730,72,21,C.gray,false);
 box(s,900,138,245,400,C.green,"roundRect");
 textBox(s,"5",940,180,165,90,72,C.white,true,"center");
 textBox(s,"operating domains",940,270,165,42,19,C.white,true,"center");
 textBox(s,"31 tests\n20 scenarios\n0% unsafe actions",934,350,177,128,22,C.mint,true,"center");
 textBox(s,"Kang Wei  |  Agentic AI Capstone  |  September 2026",78,612,730,28,16,C.gray,false);
 note(s,"Hello. I am Kang Wei, and this is HouseholdOS, an approval-gated AI Chief of Staff for family and ministry operations. The project began with a practical problem: our commitments are spread across school calendars, soccer feeds, recurring lessons, church spreadsheets, email, and LINE. HouseholdOS brings those sources into one operating view, creates a weekly brief, and keeps humans in control of every consequential action. I will show the problem, the architecture, the design decisions, the evaluation results, and what remains before production use.");
}
// 2
{
 const s=p.slides.add(); title(s,"The coordination problem",2);
 label(s,"Fragmented inputs",75,155,250); label(s,"Operational consequences",735,155,300,C.coral);
 textBox(s,"School calendars\nSoccer feeds\nRecurring lessons\nChurch spreadsheet\nPastor email\nLINE group",80,195,350,340,28,C.ink,true);
 const stem=slide=>{};
 box(s,480,260,190,145,C.mint); textBox(s,"Manual\nreview",492,283,166,92,25,C.green,true,"center");
 textBox(s,"Missed handoffs\nLate pickups\nWrong assignments\nUnreviewed messages",740,205,415,250,27,C.ink,true);
 textBox(s,"Calendars record events. They do not produce a complete operating plan.",735,500,430,76,22,C.coral,true);
 note(s,"The central issue is fragmentation. Each source is useful on its own, but the household still has to reconcile dates, time zones, travel buffers, changing drivers, volunteer assignments, and communication deadlines. A normal calendar can tell me that an event exists. It cannot tell me that one child has an overlap, that the driver is still unknown, that a Bible-study leader needs a reminder ten and a half days ahead, or that a public announcement must omit helper-only details. The cost is repeated manual work and a real risk of missed handoffs.");
}
// 3
{
 const s=p.slides.add(); title(s,"System goal and operating boundary",3);
 textBox(s,"One weekly brief across five domains",75,150,600,56,31,C.green,true);
 const items=[["Kids","conflicts and drivers"],["Church","drafts and assignments"],["Groceries","week-scoped list"],["Travel","planning lifecycle"],["Maintenance","owned due dates"]];
 items.forEach((it,i)=>{const x=78+(i%3)*380,y=238+Math.floor(i/3)*145; box(s,x,y,330,102,i===4?C.mint:C.white); textBox(s,it[0],x+18,y+14,294,34,23,C.ink,true); textBox(s,it[1],x+18,y+53,294,28,17,C.gray);});
 textBox(s,"No purchases, bookings, contractor contact, or external messages without an exact approval",78,558,1090,60,22,C.coral,true,"center");
 note(s,"The goal is one reviewable weekly brief across five domains: kids activities, church events, groceries, travel, and house maintenance. Success requires more than fluent text. The system must preserve source facts, identify conflicts and missing information, create actionable work, and keep external actions behind an approval boundary. Budget is deferred. Purchases, travel bookings, and contractor engagement are unavailable. The grocery, travel, and maintenance records shown in the capstone demo are synthetic and clearly labeled.");
}
// 4
{
 const s=p.slides.add(); title(s,"Architecture and major components",4);
 const cols=[{x:70,t:"Sources",items:"ICS feeds\nGoogle Sheets\nGmail\nManual input",fill:C.white},{x:325,t:"Deterministic core",items:"Normalization\nSQLite memory\nRetrieval filters\nPolicy checks",fill:C.mint},{x:610,t:"Agent workflow",items:"Supervisor\nSchedule\nResearch\nPlanner\nCritic",fill:C.white},{x:895,t:"Controlled actions",items:"Apps Script\nGoogle Calendar\nLINE API\nAudit record",fill:C.mint}];
 cols.forEach((c,i)=>{box(s,c.x,175,245,350,c.fill); textBox(s,c.t,c.x+20,195,205,45,23,C.green,true,"center"); textBox(s,c.items,c.x+28,270,190,205,22,C.ink,true,"center"); if(i<3) textBox(s,"›",c.x+247,300,35,60,44,C.coral,true,"center");});
 textBox(s,"Streamlit provides the operating console and visible run trace",155,565,970,48,23,C.ink,true,"center");
 note(s,"The architecture uses ports and adapters. Streamlit is the operating console. Read-only adapters ingest four ICS sources, Gmail messages, Google Sheets data, and manual input. Deterministic Python normalizes dates, expands recurrences, calculates transportation, filters evidence, and enforces policy. SQLite stores operational state, evidence, traces, approvals, and delivery outcomes. The OpenAI Agents SDK supports a supervisor plus Schedule, Research, Planner, and Critic specialists. At the action boundary, Apps Script updates the spreadsheet and calendars, while the LINE API sends an approved draft. This division keeps exact rules outside probabilistic reasoning.");
}
// 5
{
 const s=p.slides.add(); title(s,"Human-in-the-loop action flow",5);
 const steps=[["1","Draft","System prepares content"],["2","Preview","User checks facts"],["3","Approve","Exact tool and payload"],["4","Execute","Adapter sends or syncs"],["5","Record","Outcome enters audit log"]];
 steps.forEach((a,i)=>{const x=62+i*243; box(s,x,208,210,230,i===2?C.mint:C.white); textBox(s,a[0],x+65,227,80,60,38,i===2?C.green:C.coral,true,"center"); textBox(s,a[1],x+18,304,174,38,22,C.ink,true,"center"); textBox(s,a[2],x+18,352,174,54,16,C.gray,false,"center");});
 textBox(s,"Missing credentials, destinations, approval, or scheduled time causes a closed failure",110,500,1060,66,24,C.coral,true,"center");
 note(s,"Human oversight is implemented as state, not as a sentence in a prompt. The system drafts an action and presents the exact content. The user previews it, then approval binds to the specific tool and payload. Only then can the adapter execute, and the result is written to an audit record. Scheduled actions remain locked until their approved time. If a credential, destination, matching approval, or timing condition is absent, the adapter fails closed. This flow supports ministry reminders and calendar changes while preventing an accidental click from becoming an unreviewed external action.");
}
// 6
{
 const s=p.slides.add(); s.background.fill=C.green;
 textBox(s,"Live demonstration",75,70,880,70,44,C.white,true);
 textBox(s,"SANITIZED CAPSTONE INSTANCE",80,155,500,28,16,C.lime,true);
 const steps=[["1","Run weekly brief"],["2","Inspect five domains"],["3","Review exact approval payload"],["4","Run 20-scenario evaluation"]];
 steps.forEach((a,i)=>{const y=225+i*82; textBox(s,a[0],88,y,48,48,26,C.lime,true,"center"); textBox(s,a[1],160,y,820,48,25,C.white,true);});
 box(s,1010,185,190,340,C.cream); textBox(s,"DEMO\nMODE",1030,220,150,75,29,C.green,true,"center"); textBox(s,"Synthetic data\nMailbox disabled\nExternal writes disabled",1030,330,150,125,18,C.ink,true,"center");
 textBox(s,"Switch to localhost:8502, then return to the deck",80,605,900,32,19,C.mint,false);
 note(s,"Now I will switch to the sanitized HouseholdOS instance on port eighty five zero two. I will run the weekly brief, inspect the synthetic grocery, travel, and maintenance sections, review an exact approval payload, and run the twenty-scenario evaluation. Demo mode prevents mailbox access and external execution.");
}
// 7
{
 const s=p.slides.add(); title(s,"Key design decisions",7);
 const rows=[["Sheets as church SSOT","Frequent helper changes stay editable and calendar sync remains derived"],["Typed contracts plus deterministic rules","Pydantic validates state while Python owns exact dates, permissions, and constraints"],["Local-first SQLite memory","The demo runs offline and stores approvals, traces, and domain lifecycles"],["One model harness","OpenAI Agents SDK adds reasoning without overlapping LangChain or CrewAI control planes"],["Synthetic demo records","A reproducible demonstration avoids publishing private household details"]];
 rows.forEach((r,i)=>{const y=150+i*94; textBox(s,r[0],80,y,355,65,20,C.green,true); textBox(s,r[1],465,y,710,65,18,C.ink,false); if(i<4) s.shapes.add({geometry:"rect",position:{left:80,top:y+76,width:1095,height:2},fill:C.line,line:{fill:C.line,width:0}});});
 note(s,"Five decisions shaped the final system. Google Sheets remains the church system of record because helper assignments change frequently. Typed Pydantic contracts and deterministic Python enforce facts and constraints. SQLite supports a local-first demo with inspectable state. The OpenAI Agents SDK is the only model harness, avoiding overlapping orchestration frameworks. Finally, synthetic records make the grocery, travel, and maintenance demo reproducible without exposing private data. Across the program, these decisions narrowed a broad assistant concept into an evaluable operating system.");
}
// 8
{
 const s=p.slides.add(); title(s,"Evaluation approach and results",8);
 const chart=s.charts.add("bar",{position:{left:75,top:170,width:700,height:390},categories:["Unit tests","Benchmark scenarios","Unsafe actions"],series:[{name:"Observed",values:[31,20,0],fill:C.green}],barOptions:{direction:"bar",grouping:"clustered"},hasLegend:false,dataLabels:{showValue:true,position:"outEnd"}}); applyPresentationChartFont(chart,{fontFamily:font});
 box(s,825,177,355,105,C.mint); textBox(s,"31 / 31",850,190,305,42,30,C.green,true,"center"); textBox(s,"unit tests passed",850,235,305,25,17,C.gray,false,"center");
 box(s,825,302,355,105,C.white); textBox(s,"20 / 20",850,315,305,42,30,C.green,true,"center"); textBox(s,"benchmark scenarios passed",850,360,305,25,17,C.gray,false,"center");
 box(s,825,427,355,105,C.white); textBox(s,"0%",850,440,305,42,30,C.coral,true,"center"); textBox(s,"unsafe-action rate",850,485,305,25,17,C.gray,false,"center");
 textBox(s,"Synthetic fixtures test correctness. A longitudinal user study is still pending.",115,598,1050,40,19,C.gray,false,"center");
 note(s,"Evaluation combines 31 unit tests with a deterministic benchmark of twenty scenarios. The tests cover persistence, calendar repair, overlap detection, cancellations, driver overrides, ministry drafting, email extraction, source filtering, and fail-closed adapters. All 31 passed. The benchmark covers routing, constraints, missing information, transportation, retrieval, grounding, safety, synthesis, and each operating domain. It passed 20 of 20, and the unsafe-action rate was zero. These results show correctness against the implemented suite. They do not establish production reliability, and the planned user study has not yet measured time saved or trust.");
}
// 9
{
 const s=p.slides.add(); title(s,"Public repository and reproducibility",9);
 textBox(s,"Public repository",80,160,300,35,17,C.green,true); textBox(s,"github.com/tummy-wei/HouseholdOS",80,200,950,50,29,C.coral,true);
 const left="README and architecture\nStreamlit application\nDomain models and workflows\nIntegration adapters";
 const right="31 unit tests\n20-scenario baseline\nSanitized sample inputs\nDemo and setup guides";
 box(s,80,295,500,245,C.white); textBox(s,left,110,322,440,190,24,C.ink,true);
 box(s,660,295,500,245,C.mint); textBox(s,right,690,322,440,190,24,C.ink,true);
 textBox(s,"Publish only after removing tokens, private email, addresses, and live group identifiers",120,583,1040,44,19,C.gray,true,"center");
 note(s,"The public repository is available at github.com/tummy-wei/HouseholdOS. Before final publication, I will verify that credentials, OAuth tokens, private email content, addresses, and live group identifiers are excluded. The repository should contain the README, architecture, application, domain workflows, adapters, tests, benchmark baseline, sample inputs, and demo instructions. A reviewer can launch Streamlit, run the 31 tests, rerun the benchmark, and inspect the approval boundary.");
}
// 10
{
 const s=p.slides.add(); title(s,"Strengths, limitations, and next steps",10);
 label(s,"Strengths",75,150,250); label(s,"Current limitations",465,150,300,C.coral); label(s,"Next steps",860,150,250);
 textBox(s,"Visible provenance\nTyped state\nFail-closed writes\nFive-domain brief\nOffline fallback",78,195,310,310,23,C.ink,true);
 textBox(s,"Local process only\nNo job scheduler\nRule-based routing\nSynthetic evaluation\nOne-household design",468,195,310,310,23,C.ink,true);
 textBox(s,"Managed deployment\nDurable job queue\nSandbox integration tests\nFour-week user study\nSemantic retrieval",863,195,320,310,23,C.ink,true);
 textBox(s,"HouseholdOS demonstrates a reusable Chief-of-Staff pattern while keeping decisions human-owned",120,565,1040,62,23,C.green,true,"center");
 note(s,"The strongest parts of HouseholdOS are visible provenance, typed state, deterministic constraint checks, fail-closed actions, and one brief across five domains. Current limitations are equally important: it runs locally, lacks a durable scheduler, relies on rule-based calendar logic, and has mostly synthetic evaluation shaped by one household. The next steps are managed deployment, a durable job queue, sandbox integration tests, and a four-week user study. Later work can add semantic Bible-material retrieval and budget support. The transferable result is a reusable Chief-of-Staff pattern that coordinates complex work while leaving decisions with people. Thank you.");
}

const draft=path.join(TMP_DIR,"candidate.pptx");
await (await PresentationFile.exportPptx(p)).save(draft);
const result=await finalizePresentation({
  explicitTotalSlideCount:10,
  requiredNativeTableOwnerSlides:[],
  requiredNativeChartOwnerSlides:[8],
  materializeLiteralChartWorkbooks:true,
  workspaceDir,
  candidatePath:draft,
  finalPath:FINAL_PPTX,
  pythonExecutable:"/Users/tjhouse/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
  integrityValidatorPath:path.join(SKILL_DIR,"container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath:path.join(SKILL_DIR,"container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-heading-fit"],
  fontPolicy:{basis:"design",families:[font]},
  verifyArtifactToolImport:true,
  receiptPath:path.join(TMP_DIR,"validation-live-demo.json"),
});
console.log(FINAL_PPTX, result);

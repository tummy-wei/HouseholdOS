# HouseholdOS capstone movie storyboard

Target length: 9:15. Format: 1920 x 1080, 30 fps, MP4 using H.264 video and AAC audio.

## Recording safety

Launch the isolated demo on port 8502:

```bash
cd /Users/tjhouse/Projects/HouseholdOS
.venv/bin/python scripts/run_capstone_demo.py
```

Confirm the sidebar says the LINE and Calendar adapters need setup. Do not open port 8501 during recording. Close email, LINE, Calendar, and spreadsheet tabs. Hide browser bookmarks and macOS notifications.

## Timeline

| Time | Visual | Narration focus |
| --- | --- | --- |
| 0:00-0:40 | Slide 1 | Project title, five domains, measured results |
| 0:40-1:25 | Slide 2 | Fragmented inputs and consequences |
| 1:25-2:05 | Slide 3 | Goal, success conditions, operating boundary |
| 2:05-3:00 | Slide 4 | Sources, deterministic core, agents, controlled adapters |
| 3:00-3:40 | Slide 5 | Draft, preview, approval, execution, audit |
| 3:40-5:55 | Slide 6 + live demo | Weekly brief, five domain tabs, approval record, evaluation |
| 5:55-6:45 | Slide 7 | Key design decisions and design evolution |
| 6:45-7:35 | Slide 8 | 31 tests, 20 scenarios, 0% unsafe-action rate |
| 7:35-8:15 | Slide 9 | Public repository and reproducibility |
| 8:15-9:15 | Slide 10 | Strengths, limitations, next steps, close |

## Live demo clicks and words

1. Switch from slide 5 to `http://localhost:8502` and open **Weekly brief**.
2. Click **Run capstone workflow**. Say that the supervisor routes work through Schedule, Research, Planner, Critic, and final reconciliation.
3. Show the Critic score, one schedule finding, and the **Groceries**, **Travel**, and **House maintenance** tabs. State that these records are synthetic.
4. Open **Approvals**. Expand one synthetic proposed payload and explain that approval and execution are separate states. Do not execute it.
5. Open **Trace and evaluation** and run the benchmark. Point to 20/20 and the 0% unsafe-action rate.
6. Return to slide 7.

If a workflow takes longer than five seconds, narrate the architecture while it runs. Do not edit real data during the recording.

## Recommended recording method

Use PowerPoint Slide Show plus Loom or OBS. Capture the entire 1920 x 1080 screen and microphone. Start on slide 1, use slide 6 as the transition into the sanitized browser, then return to slide 7. Record in one take if possible so the demonstration remains genuinely live.

Export or download MP4. Verify the final file is between 8 and 10 minutes, contains audible human narration, shows no private data, and plays through once before uploading to YouTube as Unlisted unless the course requires Public visibility.

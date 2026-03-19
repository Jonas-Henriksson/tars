"""Seed realistic demo data into TARS JSON files + DB for UX review."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json, uuid, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent

def gid():
    return uuid.uuid4().hex[:12]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def rand_iso(start_days_ago=60, end_days_future=0):
    d = datetime.now(timezone.utc) - timedelta(days=random.randint(-end_days_future, start_days_ago))
    return d.isoformat()

def past_date(days=None):
    d = datetime.now(timezone.utc) - timedelta(days=days or random.randint(1, 14))
    return d.strftime('%Y-%m-%d')

def future_date(days=None):
    d = datetime.now(timezone.utc) + timedelta(days=days or random.randint(1, 30))
    return d.strftime('%Y-%m-%d')

OWNERS = ["Jonas", "Stefan", "Amanda", "Rodrigo", "Tim", "Oliver", "Karin", "Henrik"]

def main():
    # ─── 1. Database (user + team) ───
    db_path = ROOT / "tars.db"
    if db_path.exists():
        db_path.unlink()
        print("Removed old tars.db")

    from backend.database.engine import init_db, get_db
    from backend.auth.jwt import hash_password
    init_db()

    user_id = gid()
    team_id = gid()
    with get_db() as db:
        db.execute("INSERT INTO users (id, email, name, password_hash, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                   (user_id, "jonas@tars.ai", "Jonas", hash_password("demo123"), now_iso(), now_iso()))
        db.execute("INSERT INTO teams (id, name, owner_id, created_at, updated_at) VALUES (?,?,?,?,?)",
                   (team_id, "Executive Team", user_id, now_iso(), now_iso()))
        db.execute("INSERT INTO team_members (user_id, team_id, role) VALUES (?,?,?)",
                   (user_id, team_id, "owner"))
    print("DB: user + team created")

    # ─── 2. Themes (themes.json) ───
    themes = []
    theme_defs = [
        ("Digital Transformation & AI", "Leveraging technology to automate processes and drive innovation"),
        ("Operational Excellence", "Improving efficiency, reducing costs, and optimizing supply chain"),
        ("Growth & Market Expansion", "New markets, customer acquisition, and revenue diversification"),
    ]
    for title, desc in theme_defs:
        themes.append({
            "id": gid(), "title": title, "description": desc,
            "status": "active", "source": "confirmed",
            "created_at": rand_iso(), "updated_at": now_iso(),
        })
    (ROOT / "themes.json").write_text(json.dumps({"themes": themes}, indent=2))
    print(f"themes.json: {len(themes)} themes")

    # ─── 3. Initiatives (initiatives.json) ───
    init_defs = [
        ("AI Tooling and Infrastructure", 0, "on_track", "Jonas", "high"),
        ("Data Platform Modernization", 0, "at_risk", "Stefan", "high"),
        ("Supply Chain Optimization", 1, "on_track", "Amanda", "high"),
        ("Forecast Accuracy Program", 1, "off_track", "Rodrigo", "high"),
        ("KPI Dashboard & Reporting", 1, "on_track", "Tim", "medium"),
        ("GSO Rollout & Alignment", 2, "at_risk", "Oliver", "high"),
        ("Fulfillment Network Strategy", 2, "on_track", "Karin", "medium"),
        ("Global Planning Office", 2, "on_track", "Henrik", "medium"),
    ]
    initiatives = []
    for title, theme_idx, status, owner, priority in init_defs:
        initiatives.append({
            "id": gid(), "title": title,
            "description": f"Drive {title.lower()} across the organization",
            "owner": owner, "quarter": "Q1 2026", "status": status,
            "priority": priority, "theme_id": themes[theme_idx]["id"],
            "source": "confirmed", "milestones": [],
            "created_at": rand_iso(), "updated_at": now_iso(),
        })
    (ROOT / "initiatives.json").write_text(json.dumps({"initiatives": initiatives, "key_results": []}, indent=2))
    print(f"initiatives.json: {len(initiatives)} initiatives")

    # ─── 4. Epics & Stories (epics.json) ───
    epic_defs = [
        ("ML Pipeline Setup", 0, "in_progress", "Jonas"),
        ("LLM Integration Layer", 0, "in_progress", "Stefan"),
        ("AI Use Case Discovery", 0, "backlog", "Amanda"),
        ("Data Lake Migration", 1, "in_progress", "Stefan"),
        ("Real-time ETL Pipeline", 1, "backlog", "Rodrigo"),
        ("Data Governance Framework", 1, "in_progress", "Tim"),
        ("Inventory Visibility Dashboard", 2, "in_progress", "Amanda"),
        ("Warehouse Automation Phase 1", 2, "backlog", "Oliver"),
        ("Supplier Integration Portal", 2, "done", "Karin"),
        ("Demand Forecast Model v2", 3, "in_progress", "Rodrigo"),
        ("Forecast KPI Scope Expansion", 3, "backlog", "Tim"),
        ("Interim Reporting Flow", 3, "in_progress", "Henrik"),
        ("Executive KPI Dashboard", 4, "in_progress", "Tim"),
        ("Automated Report Generation", 4, "backlog", "Jonas"),
        ("Regional Rollout Playbook", 5, "in_progress", "Oliver"),
        ("Change Management Program", 5, "backlog", "Karin"),
        ("Fulfillment Center Design", 6, "in_progress", "Karin"),
        ("Last Mile Optimization", 6, "backlog", "Henrik"),
        ("Planning Office Charter", 7, "in_progress", "Henrik"),
        ("Resource Allocation Model", 7, "backlog", "Jonas"),
    ]
    epics = []
    stories = []
    story_statuses = ['backlog', 'ready', 'in_progress', 'in_review', 'done', 'blocked']
    story_weights = [15, 10, 30, 10, 25, 10]
    story_verbs = ['Setup', 'Integration', 'Testing', 'Documentation', 'Review', 'Deployment', 'Analysis', 'Design']

    for title, init_idx, status, owner in epic_defs:
        eid = gid()
        epics.append({
            "id": eid, "title": title, "description": f"Deliver {title.lower()}",
            "owner": owner, "initiative_id": initiatives[init_idx]["id"],
            "status": status, "priority": random.choice(["high", "medium"]),
            "quarter": "Q1 2026", "source": "confirmed",
            "acceptance_criteria": [],
            "created_at": rand_iso(), "updated_at": now_iso(),
        })
        n_stories = random.randint(2, 4)
        for j in range(n_stories):
            stories.append({
                "id": gid(), "epic_id": eid,
                "title": f"{title}: {story_verbs[j % len(story_verbs)]} phase {j+1}",
                "description": f"Implement phase {j+1} for {title.lower()}",
                "owner": random.choice([owner] * 3 + OWNERS),
                "status": random.choices(story_statuses, weights=story_weights)[0],
                "priority": random.choice(["high", "medium", "low"]),
                "size": random.choice(["S", "M", "M", "L"]),
                "source": "confirmed", "acceptance_criteria": [],
                "linked_task_ids": [],
                "created_at": rand_iso(), "updated_at": now_iso(),
            })

    (ROOT / "epics.json").write_text(json.dumps({"epics": epics, "stories": stories}, indent=2))
    print(f"epics.json: {len(epics)} epics, {len(stories)} stories")

    # ─── 5. Smart Tasks (notion_intel.json) ───
    task_descriptions = [
        "Review Q1 forecast accuracy metrics and identify deviation root causes",
        "Schedule alignment meeting with supply chain leads re: inventory targets",
        "Draft executive summary for board deck — AI initiative progress",
        "Follow up with Stefan on data lake migration blockers",
        "Prepare KPI dashboard mockup for council review",
        "Review vendor proposals for warehouse automation software",
        "Update fulfillment center cost-benefit analysis with latest numbers",
        "Send weekly status email to GSO stakeholders",
        "Coordinate with IT on production environment for ML pipeline",
        "Review and approve demand forecast model validation results",
        "Prepare change management communication plan for Q2 rollout",
        "Schedule 1:1 with Rodrigo to discuss forecast accuracy gaps",
        "Draft resource allocation proposal for Global Planning Office",
        "Review supplier integration API documentation",
        "Finalize executive KPI definitions with Tim",
        "Prepare talking points for next steering committee",
        "Follow up on open items from last week's operations review",
        "Review regional rollout timeline and flag risks",
        "Update initiative status in tracking system",
        "Coordinate cross-team dependencies for data platform work",
        "Prepare quarterly business review presentation",
        "Review and prioritize incoming decision requests",
        "Schedule architecture review for LLM integration",
        "Draft success criteria for AI use case evaluation",
        "Review last mile delivery performance metrics",
        "Prepare budget variance explanation for finance team",
        "Follow up with Karin on supplier portal go-live checklist",
        "Review ETL pipeline performance benchmarks",
        "Prepare onboarding materials for new planning office staff",
        "Schedule retrospective for completed supplier integration epic",
        "Review data governance policy draft with legal",
        "Prepare demo environment for KPI dashboard stakeholder review",
        "Follow up on open HR requests for AI team hiring",
        "Review and update risk register for all active initiatives",
        "Prepare agenda for next cross-functional sync",
        "Draft SLA proposal for data platform consumers",
        "Review testing results for demand forecast model",
        "Prepare capacity planning update for leadership team",
        "Follow up with vendors on automation pilot feedback",
        "Review and approve communication templates for GSO rollout",
        "Schedule training session for new reporting tools",
        "Prepare competitive analysis update for strategy team",
        "Review open pull requests for ML pipeline repository",
        "Follow up on blocked stories with team leads",
        "Draft post-mortem for last sprint's missed deliverables",
        "Review infrastructure cost projections for next quarter",
        "Prepare stakeholder map for fulfillment network strategy",
        "Schedule planning poker for upcoming sprint stories",
        "Review and update OKR progress for all initiatives",
        "Prepare weekly executive briefing document",
        "Follow up on outstanding procurement approvals",
        "Review security assessment results for data platform",
        "Prepare user acceptance testing plan for KPI dashboard",
        "Draft proposal for pilot AI use case with operations team",
        "Review and update project timeline for data lake migration",
        "Prepare delegation recommendations for Q2 tasks",
        "Follow up with Henrik on planning office charter feedback",
        "Review benchmark data for warehouse automation ROI",
        "Prepare summary of key decisions made this quarter",
        "Schedule alignment session with regional leads",
    ]

    topics_list = ["Supply Chain", "AI/ML", "Finance", "Operations", "Strategy", "HR", "IT"]
    smart_tasks = []
    for desc in task_descriptions:
        owner = random.choice(OWNERS)
        has_date = random.random() < 0.65
        follow_up = ""
        if has_date:
            follow_up = past_date(random.randint(1, 10)) if random.random() < 0.3 else future_date(random.randint(1, 21))

        step_options = [
            "Gather data from relevant stakeholders",
            "Draft initial proposal document",
            "Schedule review meeting",
            "Incorporate feedback from team",
            "Send final version for approval",
            "Update tracking system",
            "Follow up with assignees",
        ]
        steps = "\n".join(random.sample(step_options, random.randint(2, 4))) if random.random() < 0.5 else ""
        context = f"Discussed in operations review. {owner} mentioned this needs attention before end of month." if random.random() < 0.4 else ""

        # Link some tasks to stories
        linked_story = random.choice(stories)["id"] if random.random() < 0.35 else ""

        smart_tasks.append({
            "id": gid(),
            "description": desc,
            "owner": owner,
            "status": random.choices(["open", "done"], weights=[80, 20])[0],
            "quadrant": random.choices([1, 2, 3, 4], weights=[20, 35, 25, 20])[0],
            "topics": random.sample(topics_list, random.randint(1, 3)),
            "follow_up_date": follow_up,
            "source_title": f"Operations Review {rand_iso(14, 0)[:10]}" if random.random() < 0.4 else "",
            "source_url": "",
            "source_context": context,
            "steps": steps,
            "delegated": random.random() < 0.2,
            "story_id": linked_story,
            "classification": random.choices(["strategic", "operational", "unclassified"], weights=[40, 40, 20])[0],
            "source": random.choices(["confirmed", "auto"], weights=[70, 30])[0],
            "created_at": rand_iso(30),
        })

    # People intel data
    people_defs = [
        ("Jonas", "Chief of Staff", "Executive Office"),
        ("Stefan", "Head of Data & AI", "Technology"),
        ("Amanda", "VP Supply Chain", "Operations"),
        ("Rodrigo", "Forecast Manager", "Operations"),
        ("Tim", "BI & Analytics Lead", "Technology"),
        ("Oliver", "GSO Program Manager", "Strategy"),
        ("Karin", "Logistics Director", "Operations"),
        ("Henrik", "Planning Office Lead", "Strategy"),
        ("Marco", "Finance Controller", "Finance"),
        ("Belinda", "HR Business Partner", "HR"),
        ("Erik", "Solutions Architect", "Technology"),
        ("Matthias", "VP Operations", "Operations"),
        ("Sievo", "Procurement Lead", "Procurement"),
        ("Harald", "Regional Head EMEA", "Operations"),
        ("Manuela", "Change Management Lead", "HR"),
    ]

    intel_people = {}
    page_index = {}
    for name, role, org in people_defs:
        mentions = random.randint(5, 45)
        intel_people[name] = mentions  # people dict is {name: mention_count}
        # Create pages in page_index that reference this person
        n_pages = random.randint(2, 6)
        for i in range(n_pages):
            pid = gid()
            page_index[pid] = {
                "title": f"Meeting Notes — Week {i+10} ({name})",
                "url": "",
                "people": [name],
                "topics": random.sample(topics_list, 2),
                "last_edited": rand_iso(14),
            }

    topics_data = {}
    for topic in topics_list + ["Procurement", "Logistics", "Planning"]:
        topics_data[topic] = random.randint(8, 40)

    intel = {
        "last_scan_at": now_iso(),
        "pages_scanned": 142,
        "topics": topics_data,
        "people": intel_people,
        "smart_tasks": smart_tasks,
        "page_index": page_index,
        "executive_summary": {"overview": "Active quarter with 8 strategic initiatives across 3 themes."},
        "scan_history": [],
    }
    (ROOT / "notion_intel.json").write_text(json.dumps(intel, indent=2, default=str))
    print(f"notion_intel.json: {len(smart_tasks)} tasks, {len(intel_people)} people, {len(topics_data)} topics")

    # ─── 6. Decisions (decisions.json) ───
    decision_data = [
        ("Proceed with AWS as primary cloud provider for data platform", "decided", "Jonas", "Cost analysis favored AWS; team expertise aligned"),
        ("Delay warehouse automation Phase 1 by 2 weeks", "decided", "Amanda", "Vendor delivery delayed; adjusted timeline accordingly"),
        ("Adopt LangChain for LLM orchestration layer", "decided", "Stefan", "Best community support and flexibility for our use case"),
        ("Increase forecast accuracy target from 85% to 90%", "pending", "Rodrigo", "Board requested higher accuracy for Q2"),
        ("Approve additional headcount for AI team (2 FTE)", "pending", "Jonas", "Critical for maintaining initiative timeline"),
        ("Switch KPI dashboard from Tableau to custom React app", "decided", "Tim", "Better integration with TARS platform"),
        ("Standardize on quarterly OKR cadence across all initiatives", "decided", "Henrik", "Alignment needed for Global Planning Office launch"),
        ("Defer last mile optimization to Q2", "revisit", "Karin", "Resource constraints; revisit after fulfillment center design"),
        ("Approve vendor contract for supplier integration middleware", "decided", "Oliver", "Best price-performance ratio after RFP"),
        ("Restructure GSO rollout to region-by-region approach", "pending", "Oliver", "Full rollout too risky; phased approach reduces risk"),
        ("Consolidate reporting tools to single platform", "pending", "Tim", "Multiple tools creating confusion and data discrepancies"),
        ("Invest in real-time demand sensing capability", "revisit", "Rodrigo", "Technology maturity uncertain; needs more evaluation"),
    ]
    decisions = []
    for title, status, decided_by, rationale in decision_data:
        decisions.append({
            "id": gid(), "title": title, "rationale": rationale,
            "decided_by": decided_by,
            "stakeholders": random.sample(OWNERS, random.randint(2, 4)),
            "context": "", "initiative": "",
            "status": status, "outcome_notes": "",
            "source": "manual", "source_page_id": "",
            "linked_type": "", "linked_id": "", "linked_title": "",
            "created_at": rand_iso(30), "updated_at": now_iso(),
        })
    (ROOT / "decisions.json").write_text(json.dumps(decisions, indent=2))
    print(f"decisions.json: {len(decisions)} decisions")

    # ─── 7. People profiles (people_profiles.json) ───
    rel_types = ["colleague", "manager", "report", "stakeholder"]
    profiles = {}
    for name, role, org in people_defs:
        profiles[name] = {
            "role": role,
            "relationship": random.choice(rel_types),
            "organization": org,
            "email": f"{name.lower()}@company.com",
            "notes": "",
        }
    (ROOT / "people_profiles.json").write_text(json.dumps(profiles, indent=2))
    print(f"people_profiles.json: {len(profiles)} profiles")

    # ─── 8. Tracked tasks (notion_tracked_tasks.json) — optional extra ───
    tracked = []
    tracked_descs = [
        "Update board slides for quarterly review",
        "Submit expense reports for Q4 travel",
        "Complete compliance training module",
        "Review and sign NDA for new vendor",
        "Submit performance review for direct reports",
        "Book travel for strategy offsite",
        "Respond to IT security audit questionnaire",
        "Update team org chart",
        "Prepare new hire onboarding checklist",
        "Schedule annual team building event",
    ]
    for desc in tracked_descs:
        tracked.append({
            "id": gid(), "description": desc,
            "owner": random.choice(OWNERS),
            "status": random.choice(["open", "open", "open", "completed"]),
            "topic": random.choice(topics_list),
            "follow_up_date": future_date(random.randint(3, 20)) if random.random() < 0.6 else "",
            "source": "notion",
        })
    (ROOT / "notion_tracked_tasks.json").write_text(json.dumps(tracked, indent=2))
    print(f"notion_tracked_tasks.json: {len(tracked)} tracked tasks")

    print("\n✓ Demo data seeded successfully!")
    print(f"  Login: jonas@tars.ai / demo123")

if __name__ == "__main__":
    main()

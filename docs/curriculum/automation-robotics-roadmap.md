# Automation & Robotics Engineering Curriculum
> Fresh grad → hired junior automation engineer in 12 months

---

## Phase 1: Core Industrial Automation (Months 1–3)

### Week 1–2: PLC Fundamentals
- [ ] Learn ladder logic: contacts, coils, timers, counters, latches
- [ ] Complete 5 basic exercises:
  1. Motor start/stop with HMI
  2. Conveyor with 3 sensors and counter
  3. Traffic light sequence
  4. Tank level control with 2 pumps
  5. Packing machine with 3-station sequence
- [ ] Resource: YouTube "PLC Programming for Beginners" + TIA Portal free trial
- [ ] Deliverable: Screenshot programs in `projects/plc-dashboard/week1-2/`

### Week 3–4: Siemens S7-1200 / TIA Portal
- [ ] Install TIA Portal trial
- [ ] Create first project: S7-1200 + KTP700 HMI
- [ ] Learn: SCL structured text, analog input scaling, PID basics
- [ ] Resource: Siemens Industry Mall e-learning
- [ ] Deliverable: Analog temperature control with HMI trend

### Week 5–6: Mitsubishi FX Series
- [ ] Download GX Works3 trial
- [ ] Learn differences from Siemens
- [ ] Convert one Siemens program to Mitsubishi
- [ ] Resource: Mitsubishi Electric FA e-learning

### Week 7–8: Electrical Fundamentals
- [ ] Read electrical schematics (IEC standard)
- [ ] Learn: sensors (proximity, photoelectric, encoders), VFDs, motor control
- [ ] Study safety circuits: E-stop, safety relays, ISO 13850
- [ ] Resource: SICK sensor catalog, Festo pneumatics basics
- [ ] Deliverable: Draw a simple motor control schematic in AutoCAD

### Milestone 1
- [ ] 3 PLC programs on GitHub
- [ ] 1 electrical schematic
- [ ] Can explain ladder logic in interview

---

## Phase 2: Industrial Robots (Months 3–6)

### Week 9–10: Fanuc Robotics
- [ ] Install ROBOGUIDE trial
- [ ] Learn: jogging, point recording, TP programming, I/O interfacing
- [ ] Build: simple pick-and-place with 4 points
- [ ] Resource: Fanuc America e-learning (free)

### Week 11–12: Yaskawa Motoman
- [ ] Install MotoSim trial
- [ ] Learn: INFORM language basics, job creation, I/O mapping
- [ ] Build: arc welding path simulation
- [ ] Resource: Yaskawa Academy

### Week 13–14: ABB RobotStudio
- [ ] Install RobotStudio free
- [ ] Learn: RAPID programming, offline simulation, collision detection
- [ ] Build: palletizing routine with 2 robots
- [ ] Resource: ABB Robotics YouTube

### Week 15–16: Kinematics + IK (Your Strength)
- [ ] Review DH parameters from RVC3
- [ ] Implement analytical IK for 6-DOF arm in Python/NumPy
- [ ] Compare with numerical IK (Jacobian)
- [ ] Visualize in Matplotlib or RViz
- [ ] Resource: Your RVC3 notes + PyBullet docs
- [ ] Deliverable: GitHub repo `robot-ik-solver`

### Milestone 2
- [ ] 3 robot simulation projects
- [ ] 1 kinematics/IK implementation
- [ ] Can explain difference between Fanuc TP and ABB RAPID

---

## Phase 3: Integration (Months 6–8)

### Week 17–18: Industrial Networks
- [ ] PROFINET: configure S7-1200 + G120 VFD
- [ ] Modbus TCP: Python script reading PLC registers
- [ ] Ethernet/IP: basic Allen-Bradley setup
- [ ] Resource: manufacturer documentation

### Week 19–20: SCADA / Dashboard
- [ ] Ignition Edge free tier: create HMI for conveyor system
- [ ] Or: Python dashboard with Dash/Streamlit
- [ ] Connect to simulated PLC data
- [ ] Deliverable: Working SCADA screen

### Week 21–22: IIoT + OPC UA
- [ ] Set up OPC UA server on Raspberry Pi
- [ ] Python client reading/writing tags
- [ ] Understand MQTT basics
- [ ] Resource: OPC Foundation webinars

### Week 23–24: Your Differentiator
- [ ] Build: PLC → Python → Supabase → Next.js dashboard
- [ ] LINE notification integration (reuse TonpaiICE pattern)
- [ ] Real-time charts + alarm system
- [ ] Deploy to Vercel
- [ ] Deliverable: `automation-dashboard` repo + live URL

### Milestone 3
- [ ] Integration demo with dashboard
- [ ] PLC-robot communication working
- [ ] Dashboard deployed and shareable

---

## Phase 4: Practical Skills (Months 8–10)

### Week 25–26: Safety & Standards
- [ ] Study ISO 10218 (robot safety)
- [ ] Study ISO 13849 (safety circuits)
- [ ] LOTO procedures
- [ ] Thai labor safety regulations
- [ ] Deliverable: Safety checklist document

### Week 27–28: Pneumatics & Mechanical
- [ ] SMC/Festo pneumatics e-learning
- [ ] Design: simple pick-and-place pneumatic circuit
- [ ] Learn: robot installation, alignment, levelling
- [ ] Resource: manufacturer installation manuals

### Week 29–30: Commissioning
- [ ] Study commissioning checklists
- [ ] Simulate: 3-day startup sequence for new robot cell
- [ ] Practice: common troubleshooting scenarios
- [ ] Resource: YouTube "Robot Commissioning Checklist"

### Week 31–32: CAD
- [ ] SolidWorks student license
- [ ] Design: simple end-effector/gripper for 6-DOF arm
- [ ] Model: basic robot cell layout
- [ ] Deliverable: STEP files + render images

### Milestone 4
- [ ] Safety documentation
- [ ] CAD portfolio
- [ ] Commissioning plan document

---

## Phase 5: Portfolio & Interview Prep (Months 10–12)

### Week 33–36: Polish Portfolio
- [ ] Create GitHub profile README
- [ ] Document 4 best projects with screenshots/videos
- [ ] Write blog post: "Building an automation dashboard with Next.js + Supabase"
- [ ] Record 2-minute demo video of robot simulation

### Week 37–40: Interview Prep
- [ ] Practice PLC logic puzzles (10 standard problems)
- [ ] Study electrical safety Q&A
- [ ] Prepare answers for:
  - "Tell me about a time you solved a difficult technical problem"
  - "Why automation?"
  - "Can you work overtime / travel?"
- [ ] Mock interviews with friends or online

### Week 41–44: Applications
- [ ] Target 30 applications
- [ ] Companies: UTAC, Fabrinet, Seagate, Delta, Audaxia, local integrators
- [ ] Tailor CV for each: emphasize PLC, robot simulation, or dashboard as relevant
- [ ] Use LinkedIn + JobsDB + direct company websites

### Milestone 5
- [ ] 4 portfolio projects on GitHub
- [ ] CV finalized
- [ ] 30+ applications submitted

---

## Weekly Schedule (18–26 hrs/week)

| Day | Hours | Activity |
|-----|-------|----------|
| Mon | 3 hrs | PLC simulation + ladder logic |
| Tue | 2 hrs | Robot brand tutorial |
| Wed | 3 hrs | Project building |
| Thu | 2 hrs | Electrical / safety study |
| Fri | 2 hrs | RVC3 / kinematics theory |
| Sat | 4 hrs | Deep work: major project |
| Sun | 2–3 hrs | Review + English / soft skills |

---

## Resources

### PLC
- Siemens TIA Portal trial: https://new.siemens.com/global/en/products/automation/topic-areas/tia-portal.html
- Mitsubishi GX Works3: https://www.mitsubishielectric.com/app/fa/download/
- Automation Direct: free PLC learning resources

### Robots
- Fanuc ROBOGUIDE: https://www.fanuc.eu/uk/en/robots/robot-software/roboguide
- ABB RobotStudio: https://new.abb.com/products/robotics/robotstudio
- Yaskawa MotoSim: https://www.yaskawa.com/products/robot-simulators

### Electrical
- SICK sensor catalog: https://www.sick.com/
- Festo pneumatics: https://www.festo.com/
- "Electrical Controls for Automation" — various free PDFs

### Simulation
- PyBullet: https://pybullet.org/
- CoppeliaSim: https://www.coppeliarobotics.com/
- Visual Components: student license available

### CAD
- SolidWorks student: https://www.solidworks.com/student-access
- Fusion 360 free for students: https://www.autodesk.com/education/edu-software/

---

## Tracking

Update this file weekly. Mark completed items with [x].

Current week: 1
Start date: _________
Target end date: _________

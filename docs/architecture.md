# Architecture Documentation

## System Architecture

CANoe Automated Testing Agent follows a **multi-agent pipeline** architecture where data flows through four sequential sub-agents, each responsible for a distinct phase of the testing lifecycle.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Pipeline Controller                          │
│                     (src/main.py: run_pipeline)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     │
│  │  Stage1 │────▶│  Stage2 │────▶│  Stage3 │────▶│  Stage4 │     │
│  │  DBC    │     │  Signal │     │  CAPL   │     │  Verify │     │
│  │  Parse  │     │  Reason │     │  Gen    │     │  & Rpt  │     │
│  └─────────┘     └─────────┘     └─────────┘     └─────────┘     │
│       │               │               │               │             │
│       ▼               ▼               ▼               ▼             │
│   DBCModel     DependencyGraph   CAPL Scripts   Test Report       │
│   ValidResult  MuxSequences                     (HTML/JSON)       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Stage Details

### Stage 1: DBC Parse Agent (`src/agents/dbc_parser_agent.py`)

**Input:** DBC file path  
**Output:** Validated DBCModel + ValidationResult

The DBC Parse Agent reads `.dbc` files and extracts structured data:

- **Parser** (`src/dbc/parser.py`): Regex-based DBC line parser supporting:
  - `BO_` Message definitions
  - `SG_` Signal definitions (including multiplexer indicators M/m)
  - `BU_` Node definitions
  - `VAL_` Value table definitions
  - `CM_` Comments

- **Validator** (`src/dbc/validator.py`): Multi-level validation:
  - Per-signal: bit range, byte order, factor/offset, naming
  - Per-message: signal overlap, multiplexing consistency
  - Cross-message: duplicate IDs, naming conflicts

- **Models** (`src/dbc/models.py`): Data structures:
  - `DBCModel` → `MessageDefinition` → `SignalDefinition`
  - `ValidationResult` → `ValidationIssue` with severity levels

### Stage 2: Signal Reasoner Agent (`src/agents/signal_reasoner_agent.py`)

**Input:** DBCModel  
**Output:** DependencyGraph + MuxSwitchSequences

The Signal Reasoner performs "long-chain reasoning" through multiple analysis steps:

1. **Signal Node Registration**: Create graph nodes for all signals
2. **Multiplexer Dependency**: Add edges from mux signals to muxed signals
3. **Cross-Message Detection**: Identify signal dependencies across messages
4. **Topological Ordering**: Compute safe execution order
5. **Mux Coverage Analysis**: Generate switch sequences for full coverage

Key components:
- **DependencyAnalyzer** (`src/signal/dependency_analyzer.py`): NetworkX-based graph
- **MultiplexHandler** (`src/signal/mux_handler.py`): Mux group management

### Stage 3: CAPL Generator Agent (`src/agents/capl_generator_agent.py`)

**Input:** DBCModel + DependencyGraph  
**Output:** CAPL scripts (signal simulation + diagnostic test)

Generates two types of CAPL scripts:

1. **Signal Simulation Script**:
   - Message variable declarations
   - Signal initialization
   - Cyclic message output timers
   - Signal test sequence with min/max boundary testing

2. **Diagnostic Test Script**:
   - UDS service test cases (0x10/0x11/0x22/0x27/0x2E/0x31/0x19/0x14)
   - Session control pre-conditions
   - Security access sequences (simplified: fixed seed)
   - Response verification with NRC handling

OEM specification is applied through:
- **OEMRulesEngine** (`src/capl/oem_rules.py`): Service rules, naming conventions, timeouts
- **Jinja2 Templates** (`src/capl/templates/`): Parameterized CAPL generation

### Stage 4: Verification Agent (`src/agents/verification_agent.py`)

**Input:** CAPL scripts  
**Output:** VerificationReport + HTML/JSON test reports

Closes the loop through:

1. **CANoe Interface** (`src/verification/canoe_interface.py`):
   - COM automation for CANoe control
   - Simulation mode fallback when CANoe unavailable
   - Message send/receive, signal read operations

2. **Bus Data Comparator** (`src/verification/comparator.py`):
   - Expected vs. actual signal value comparison
   - Configurable tolerance (percentage-based)
   - Per-signal tolerance override support

3. **Simulation Controller** (`src/verification/simulator.py`):
   - Test step execution engine
   - Send → Wait → Verify cycle management

4. **Report Generator** (`src/report/generator.py`):
   - HTML report with styled cards, progress bars, signal table
   - JSON report for programmatic consumption
   - Metadata tracking (project, target, timestamps)

## Data Flow

```
.dbc file
    │
    ▼
[DBCParser] ─── DBCModel ────────────────────────────────┐
    │                                                     │
    ▼                                                     │
[DBCValidator] ── ValidationResult                        │
                                                          │
    ┌────────────────────────────────────────────────────┘
    ▼
[SignalDependencyAnalyzer] ── DependencyGraph ────────────┐
    │                                                     │
[MultiplexHandler] ── MuxSwitchSequences                  │
                                                          │
    ┌────────────────────────────────────────────────────┘
    ▼
[CAPLGenerator + OEMRulesEngine] ── CAPL Scripts ────────┐
    │   signal_sim.capl                                   │
    │   diag_test.capl                                    │
                                                          │
    ┌────────────────────────────────────────────────────┘
    ▼
[SimulationController + CANoeInterface] ── BusData
    │
[BusDataComparator] ── ComparisonReport
    │
    ▼
[ReportGenerator] ── test_report.html + test_report.json
```

## Configuration

- `config/default.yaml`: Default settings for all modules
- `config/oem_specs/bcm_spec.yaml`: BCM-specific OEM specification
- `examples/config/bcm_test.yaml`: Test case configuration

## Extension Points

1. **New OEM Specifications**: Add YAML files to `config/oem_specs/`
2. **New CAPL Templates**: Add Jinja2 templates to `src/capl/templates/`
3. **Custom Validation Rules**: Extend `DBCValidator` with new check methods
4. **Report Formats**: Add new generators in `src/report/`
5. **Bus Types**: Extend `CANoeInterface` for LIN/FlexRay support

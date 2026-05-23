---
layout: default
title: Hazards & forwarding
sidebar: architecture
permalink: /architecture/hazards/
---

<script src="https://cdnjs.cloudflare.com/ajax/libs/wavedrom/3.1.0/skins/default.js" type="text/javascript"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/wavedrom/3.1.0/wavedrom.min.js" type="text/javascript"></script>
<script>
  window.addEventListener('load', function () { WaveDrom.ProcessAll(); });
</script>

# Hazards & forwarding

A pipelined CPU has multiple instructions in flight at once, and those instructions can step on each other. A later instruction can need a result a producer hasn't yet written back, or a branch can resolve only after instructions fetched behind it have already entered the pipeline. This page documents the cases the core has to handle, the cycle penalty each one costs, and the SystemVerilog that handles them. The cross-stage glue lives in [`src/hazard_unit.sv`](https://github.com/cshieldsce/riscv-5/blob/main/src/hazard_unit.sv) and [`src/forwarding_unit.sv`](https://github.com/cshieldsce/riscv-5/blob/main/src/forwarding_unit.sv).

<div class="callout note"><span class="title">Cycle indexing in the diagrams below</span>
The WaveDrom diagrams use 0-indexed cycles, which is the convention in hardware textbooks. Cycle 0 is the first clock cycle in which the first instruction is fetched; an instruction fetched in cycle <code>N</code> is in decode at cycle <code>N+1</code> and in execute at cycle <code>N+2</code>.
</div>

## Summary table {#summary}

<div class="hazard-table" markdown="1">

| Hazard type | Scenario | Hardware action | Penalty (cycles) |
|---|---|---|---|
| Data | Register dependency (ALU to ALU) | Forwarding | 0 |
| Data | Store dependency (WB to MEM) | Store-data forwarding in MEM | 0 |
| Data | Load-use dependency | Stall + forwarding | 1 |
| Control | Conditional branch (taken) | Flush IF & ID | 2 |
| Control | JAL (unconditional jump) | Flush IF | 1 |
| Control | JALR (indirect jump) | Flush IF & ID | 2 |
| Combined | ALU-to-branch dependency | Stall + flush IF/ID | 3 (total) |

</div>

## Data hazards {#data-hazards}

A data hazard happens when an instruction reads a register before an earlier instruction has written its result back to the register file. The fix is to bypass the value directly out of a later pipeline register into the consuming EX stage, instead of waiting for the value to round-trip through writeback and the register file.

### Case 1: EX-to-EX forwarding {#case1}

The result that the consumer needs is exactly one cycle ahead, sitting in the EX/MEM pipeline register at the moment the consumer enters EX.

```asm
addi x1, x10, 5  # result moves into EX/MEM at end of EX
sub  x2, x1, x3  # needs x1 NOW in its EX stage
```

<div style="text-align: center;">
<script type="WaveDrom">
{ "signal": [
  { "name": "CLK", "wave": "p...." },
  { "name": "IF (Fetch)",     "wave": "345xx", "data": ["ADDI", "SUB", "OR"] },
  { "name": "ID (Decode)",    "wave": "x345x", "data": ["ADDI", "SUB", "OR"] },
  { "name": "EX (Execute)",   "wave": "xx375", "data": ["ADDI", "SUB", "OR"] },
  { "name": "MEM (Memory)",   "wave": "xxx34", "data": ["ADDI", "SUB", "OR"] },
  { "name": "WB (Writeback)", "wave": "xxxx3", "data": ["ADDI", "SUB"] },
  {},
  { "name": "Forward A Select", "wave": "xxx4x", "data": ["FORWARD"] }
],
  "head": { "text": "EX-to-EX Forwarding (Bypassing at Cycle 3)", "tick": 0 },
  "config": { "hscale": 2.2 },
  "style": {
    "4": "fill:#f0f; stroke:#f0f; stroke-width:2;"
  }
}
</script>
</div>
<br>

The forwarding unit notices that the destination of the instruction currently in EX/MEM matches the consumer's source register, and routes the EX/MEM ALU result back into the consumer's A input on the same cycle.

```verilog
// src/forwarding_unit.sv
if (ex_mem_reg_write && (ex_mem_rd != 0) && (ex_mem_rd == id_ex_rs1))
    forward_a = 2'b10; // Select data from EX/MEM register
```

### Case 2: MEM-to-EX forwarding {#case2}

The dependency is two instructions apart. The producer's result has already moved past EX/MEM and is sitting in MEM/WB when the consumer needs it.

```asm
addi x1, x10, 5
or   x4, x5, x6   # unrelated
sub  x2, x1, x3   # needs x1
```

```verilog
// src/forwarding_unit.sv
logic mem_match, ex_match;

mem_match = mem_reg_write && (mem_rd != 5'b0) && (mem_rd == rs);
ex_match  = reg_write    && (mem_rd != 5'b0) && (mem_rd == rs);

if (mem_match && !ex_match) begin : MEMHazard
  return 1'b1;
end else begin : NoMEMHazard
  return 1'b0;
end
```

The forwarding unit selects `2'b01`, bypassing the MEM/WB value directly into EX. The `!ex_match` guard ensures that when both forwarding paths could fire (Case 1 and Case 2 simultaneously), the fresher EX/MEM value wins. Priority logic lives in `src/forwarding_unit.sv` (shown below in Implementation).

### Case 3: Store-data forwarding (WB to MEM) {#case3}

A store needs its data operand `rs2` in MEM, but the value is still in WB. The MEM stage has its own small forwarding path for this so the surrounding pipeline doesn't have to stall.

```asm
addi x1, x0, 10
sw   x1, 0(x2)   # sw needs x1, which is in WB this cycle
```

```verilog
// src/mem_stage.sv
if (wb_reg_write && (wb_rd != 5'b0) && (wb_rd == mem_rs2)) begin
  return wb_data;
end else begin
  return mem_data;
end
```

This is why the EX/MEM register carries `rs2` through to MEM in addition to the data: the forwarding compare needs to know what register the store is reading from. Without that, store-after-load sequences would force an unnecessary stall.

## The one data hazard forwarding cannot fix {#data-hazards-cannot}

### Case 4: Load-use stall {#case4}

When the consumer's source is the destination of an immediately-preceding load, the load's value isn't ready until the end of MEM. The consumer is already in EX needing the operand a cycle earlier. Forwarding doesn't help; the value just isn't computed yet. The hazard unit detects this case in ID, stalls IF and ID for one cycle, and inserts a NOP into EX (the "bubble"). After the bubble, the value lands at the MEM-stage boundary and Case 1 or Case 2 forwarding takes it from there.

```asm
lw   x1, 0(x10)   # load into x1
add  x2, x1, x3   # uses x1 immediately (stall needed)
or   x4, x5, x6   # unrelated
sub  x7, x1, x8   # uses x1 (no stall; forwarding handles it)
```

<div style="text-align: center;">
<script type="WaveDrom">
{ "signal": [
  { "name": "CLK", "wave": "p....." },
  { "name": "IF (Fetch)",     "wave": "34697x", "data": ["LW", "ADD", "OR", "OR", "SUB"] },
  { "name": "ID (Decode)",    "wave": "x34967", "data": ["LW", "ADD", "ADD", "OR", "SUB"] },
  { "name": "EX (Execute)",   "wave": "xx3546", "data": ["LW", "NOP", "AND", "OR" ] },
  { "name": "MEM (Memory)",   "wave": "xxx354", "data": ["LW", "NOP", "AND"] },
  { "name": "WB (Writeback)", "wave": "xxxx35", "data": ["LW", "NOP"] },
  {},
  { "name": "PIPELINE STATE", "wave": "xx345x", "data": ["DETECT", "STALL", "RESUME"] }
],
  "node": "b....",
  "edge": [ "a~>b Stall Active" ],
  "head": { "text": "Load-Use Hazard (1-Cycle Stall)", "tick": 0 },
  "config": { "hscale": 2.2 },
  "style": {
    "4": "fill:#0dd; stroke:#0dd; stroke-width:2;",
    "7": "fill:#f90; stroke:#f90; stroke-width:2;"
  }
}
</script>
</div>
<br>

The penalty is one cycle, not the worst case. The third instruction (`or`) and the fourth instruction (`sub`) shown above resolve through Case 2 / Case 1 forwarding with no further stalls.

## Control hazards {#control-hazards}

A control hazard happens when a branch or indirect jump changes the PC after fetch has already pulled in instructions from the not-taken path. The core's policy is predict-not-taken: keep fetching sequentially, and if a branch turns out to be taken, throw away the speculatively-fetched instructions.

### Case 5: Branch misprediction (2-cycle flush) {#case5}

The branch resolves in EX. By that time, two instructions sit behind it in IF and ID. If the branch is taken, both have to be replaced with NOPs (flushed) and IF is redirected to the branch target.

```asm
beq  x1, x2, target  # taken
addi x3, x0, 1       # Wrong1 (flushed)
addi x4, x0, 2       # Wrong2 (flushed)
...
target:
sub  x5, x5, x6      # target
```

<div style="text-align: center;">
<script type="WaveDrom">
{ "signal": [
  { "name": "CLK", "wave": "p....." },
  { "name": "IF (Fetch)",     "wave": "34867x", "data": ["BEQ", "Wrong1", "Wrong2", "Target", "Next"] },
  { "name": "ID (Decode)",    "wave": "x34567", "data": ["BEQ", "Wrong1", "NOP", "Target", "Next"] },
  { "name": "EX (Execute)",   "wave": "xx3556", "data": ["BEQ", "NOP", "NOP", "Target"] },
  { "name": "MEM (Memory)",   "wave": "xxx355", "data": ["BEQ", "NOP", "NOP"] },
  {},
  { "name": "Branch Taken",   "wave": "xx10xx" },
  { "name": "Pipeline Action","wave": "xx35xx", "data": ["RESOLVE", "FLUSH", "Resume"] }
],
  "node": "b..",
  "edge": [ "a~>b Flush Active" ],
  "head": { "text": "Branch Taken (2-Cycle Flush)", "tick": 0 },
  "config": { "hscale": 2.2 },
  "style": {
    "4": "fill:#0dd; stroke:#0dd; stroke-width:2;",
    "5": "fill:#0dd; stroke:#0dd; stroke-width:2;",
    "8": "fill:#f90; stroke:#f90; stroke-width:2;"
  }
}
</script>
</div>
<br>

JAL gets resolved early in ID (its target is just `PC + Imm`), so the JAL penalty is only one flushed instruction in IF, not two. JALR is indirect and resolves in EX with the same two-cycle penalty as a taken conditional branch. See the [PC selection priority]({{ '/architecture/stages/' | relative_url }}#fetch) on the Pipeline Stages page for how IF chooses between these sources.

### Case 6: ALU-to-branch stall (3-cycle combined penalty) {#case6}

If a branch's source operand is produced by the immediately preceding ALU op, the branch comparison needs a value that isn't ready until the producer reaches the end of EX. The hazard unit handles this by stalling the branch in ID for one cycle so the producer can complete EX, and then resolving the branch normally. If the branch is then taken, the standard two-cycle flush follows.

```asm
addi x1, x0, 10
beq  x1, x2, label  # depends on x1 immediately
```

<div class="callout warn"><span class="title">Why this is one extra cycle, not zero</span>
A more aggressive implementation would forward the ALU-stage result directly into the branch comparator. I chose to stall instead because it keeps the comparator logic isolated from the rest of the forwarding network and keeps the timing path simpler. The cost is one cycle when this pattern hits; the win is a cleaner critical path through the comparator.
</div>

Total worst-case penalty for an ALU-dependent taken branch: 1 cycle (stall) + 2 cycles (flush) = 3 cycles.

## How the units are wired {#implementation}

### Hazard unit ([`src/hazard_unit.sv`](https://github.com/cshieldsce/riscv-5/blob/main/src/hazard_unit.sv))

The hazard unit watches what's in flight and decides when to freeze stages or insert bubbles.

```verilog
// Load-Use Detection
if (id_ex_mem_read && ((id_ex_rd == id_rs1) || (id_ex_rd == id_rs2))) begin
    stall_if = 1'b1;
    stall_id = 1'b1;
    flush_ex = 1'b1;
end

// Branch Flush Detection
if (branch_taken_ex) begin
    flush_id = 1'b1;
    flush_ex = 1'b1;
end
```

### Forwarding unit ([`src/forwarding_unit.sv`](https://github.com/cshieldsce/riscv-5/blob/main/src/forwarding_unit.sv))

Priority matters when more than one forwarding source could fire: the EX/MEM result is fresher than the MEM/WB result, so it wins.

```verilog
// Priority: EX/MEM (most recent) > MEM/WB (older)
if (has_ex_hazard) begin
    forward_a = 2'b10;
end else if (has_mem_hazard) begin
    forward_a = 2'b01;
end
```

The same priority logic runs independently for both source operands (`forward_a` and `forward_b`), so a consumer can pull one operand from EX/MEM and the other from MEM/WB on the same cycle.

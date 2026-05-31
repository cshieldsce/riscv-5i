---
layout: default
title: Pipeline stages
sidebar: architecture
permalink: /architecture/stages/
---

# Pipeline stages

Each pipeline stage is its own SystemVerilog module under [`src/`](https://github.com/cshieldsce/riscv-5i/tree/main/src). Top-level wiring lives in [`pipelined_cpu.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/pipelined_cpu.sv). This page walks through what each stage does, why the logic looks the way it does, and shows the RTL that implements it. The [Hazards & Forwarding]({{ '/architecture/hazards/' | relative_url }}) page covers the cross-stage logic (forwarding paths, stalls, flushes) that keeps the pipeline correct.

## The complete datapath {#overview}

<div class="img-wrapper diagram">
  <img src="{{ '/images/pipeline_complete.svg' | relative_url }}" alt="Complete riscv-5i datapath with pipeline registers, forwarding paths, and hazard detection logic">
  <span class="caption">Figure 1: The full datapath, including pipeline registers, the forwarding multiplexers in EX, and the hazard-detection wires that drive stalls and flushes. Based on Patterson & Hennessy Figure 4.51 and instantiated in <a href="https://github.com/cshieldsce/riscv-5i/blob/main/src/pipelined_cpu.sv"><code>src/pipelined_cpu.sv</code></a>.</span>
</div>

<div class="pipeline-arrow"></div>

## Instruction Fetch (IF) {#fetch}

Implemented in [`src/if_stage.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/if_stage.sv). The IF stage holds the program counter, picks the address of the next instruction, and emits the current PC plus `PC+4` to the next stage.

<div class="img-wrapper">
  <img src="{{ '/images/stage_if.svg' | relative_url }}" alt="IF stage block diagram: PC register, +4 adder, and the 5-way next-PC multiplexer">
  <span class="caption">Figure 2: IF stage. The next-PC mux selects between the five inputs in priority order; the chosen value latches into the PC register on the next clock edge.</span>
</div>

### PC selection priority

Five possible next-PC sources are arbitrated by priority. Highest priority wins; the rest are ignored on that cycle.

1. Stall keeps the current PC. Triggered by a load-use hazard or any other stall condition.
2. JALR takes the indirect jump target produced by the ALU in EX.
3. Branch takes the conditional-branch target computed in EX, when the branch was resolved as taken.
4. JAL takes the direct jump target computed early in ID (the target is just `PC + Imm`).
5. Sequential, the default, takes `PC + 4`.

Resolving JAL in ID rather than waiting for EX costs one cycle of fetch penalty instead of two; see [Hazards Case 5]({{ '/architecture/hazards/' | relative_url }}#case5). JALR and conditional branches still cost two because their targets depend on register-file or ALU outputs that aren't ready until EX.

<div class="callout note"><span class="title">Why JAL is faster than JALR</span>
JAL's target is <code>PC + Imm</code> with both operands available immediately after decode. JALR's target is <code>rs1 + Imm</code>, which has to wait on the register file (or a forwarded value) and the ALU. Same instruction family, different dependency chain, different penalty.
</div>

```verilog
// --- Next PC Logic ---
logic [XLEN-1:0] if_pc_reg;
logic [XLEN-1:0] if_next_pc;
logic [XLEN-1:0] if_pc_plus_4_calc;

assign if_pc_plus_4_calc = if_pc_reg + 4;

// -- Select Next PC based on control signals ---
always_comb begin: SelectNextPC
    if (stall) begin : Stalled
        if_next_pc = if_pc_reg;
    end else if (jalr_taken) begin : JALRTaken
        if_next_pc = jalr_target;
    end else if (branch_taken) begin : BranchTaken
        if_next_pc = branch_target;
    end else if (jal_taken) begin : JALTaken
        if_next_pc = jal_target;
    end else begin : IncrementPC
        if_next_pc = if_pc_plus_4_calc;
    end
end

// -- Update or Hold PC ---
always_ff @(posedge clk) begin : PC_Register
    if (rst) begin : ResetPC
        if_pc_reg <= {XLEN{1'b0}};
    end else begin : UpdatePC
        if_pc_reg <= if_next_pc;
    end
end

// --- Outputs ---
assign pc_out          = if_pc_reg;
assign pc_plus_4       = if_pc_plus_4_calc;
assign instruction_out = instruction_in;
```

<div class="pipeline-arrow"></div>

## Instruction Decode (ID) {#decode}

Implemented in [`src/id_stage.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/id_stage.sv). The ID stage chops the 32-bit instruction word into its fields, generates the control signals for downstream stages, reads `rs1` and `rs2` from the register file, and produces the sign-extended immediate via [`src/imm_gen.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/imm_gen.sv).

<div class="img-wrapper">
  <img src="{{ '/images/stage_id.svg' | relative_url }}" alt="ID stage block diagram: instruction field decomposition, control unit, register file, and immediate generator">
  <span class="caption">Figure 3: ID stage. The control unit, register file, and immediate generator all run in parallel on the same instruction word.</span>
</div>

### Instruction field extraction

```verilog
assign opcode = opcode_t(instruction[6:0]);
assign rd     = instruction[11:7];
assign funct3 = instruction[14:12];
assign rs1    = instruction[19:15];
assign rs2    = instruction[24:20];
assign funct7 = instruction[31:25];
```

The opcode and `funct3`/`funct7` fields drive `src/control_unit.sv`, which emits the control bundle (`reg_write`, `mem_write`, `alu_control`, `op_a_sel`, `op_b_sel`, `wb_mux_sel`, branch and jump flags) that follows the instruction through the pipeline registers.

`ImmGen` handles the five immediate encodings RV32I uses: I-type, S-type, B-type, U-type, and J-type. Each format extracts a different set of bits and sign-extends differently; the module's job is to make every immediate look like a 32-bit signed value to downstream logic.

<div class="callout note"><span class="title">ISA reference</span>
Instruction formats and field positions: <em>RISC-V Unprivileged ISA Specification v20191213</em>, Section 2. The encodings the immediate generator implements are summarized in Section 2.3 ("Immediate Encoding Variants").
</div>

<div class="pipeline-arrow"></div>

## Execute (EX) {#execute}

Implemented in [`src/ex_stage.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/ex_stage.sv). EX is where every RV32I arithmetic, logical, comparison, and shift operation happens, and where branch direction gets resolved. It is also the consumer of the forwarding paths from MEM and WB.

<div class="img-wrapper">
  <div class="figure-placeholder" role="img" aria-label="Figure pending: EX stage datapath">
    <span class="placeholder-tag">Figure pending</span>
    <span class="placeholder-detail">EX stage datapath</span>
  </div>
  <span class="caption">Figure 4 (pending): EX stage showing the forwarding multiplexers, ALU source multiplexers, and the branch-resolution block.</span>
</div>

### Forwarding multiplexers

`forwarding_unit.sv` produces a 2-bit `forward_a`/`forward_b` per source operand. The mux in EX uses those selectors to pull the freshest copy of each operand from the register file, the EX/MEM register, or the MEM/WB register.

```verilog
always_comb begin : ForwardA_MUX
    case (forward_a)
        2'b00:   ex_alu_in_a_fwd = rs1_data;           // No hazard (Register)
        2'b01:   ex_alu_in_a_fwd = wb_write_data;      // Forward from WB
        2'b10:   ex_alu_in_a_fwd = ex_mem_alu_result;  // Forward from MEM
        default: ex_alu_in_a_fwd = rs1_data;
    endcase
end
```

### ALU source multiplexers

`op_a_sel` covers the special cases where the A input isn't a register: AUIPC routes the PC into A, and LUI routes a constant zero into A.

```verilog
always_comb begin : ALUInputA_MUX
    case (op_a_sel)
        2'b00:   ex_alu_in_a = ex_alu_in_a_fwd;  // Regular register op
        2'b01:   ex_alu_in_a = pc;               // AUIPC: PC
        2'b10:   ex_alu_in_a = {XLEN{1'b0}};     // LUI: Zero
        default: ex_alu_in_a = ex_alu_in_a_fwd;
    endcase
end

assign ex_alu_in_b = op_b_sel ? imm : rs2_data_forwarded;
```

<div class="callout tip"><span class="title">LUI without a dedicated unit</span>
LUI defines <code>rd = imm &lt;&lt; 12</code>. By driving the ALU with <code>A = 0</code> and <code>B = (imm &lt;&lt; 12)</code> (the immediate generator already produces the shifted value for U-type), the ordinary ADD operation produces the correct result. No extra ALU op-code or shifter is needed for LUI specifically.
</div>

### Branch resolution

```verilog
always_comb begin
    if (branch_en) begin
        case (funct3)
            F3_BEQ:  branch_taken = alu_zero;        // A == B
            F3_BNE:  branch_taken = ~alu_zero;       // A != B
            F3_BLT:  branch_taken = alu_result[0];   // A < B (signed)
            F3_BGE:  branch_taken = ~alu_result[0];  // A >= B (signed)
            F3_BLTU: branch_taken = alu_result[0];   // A < B (unsigned)
            F3_BGEU: branch_taken = ~alu_result[0];  // A >= B (unsigned)
            default: branch_taken = 1'b0;
        endcase
    end else begin
        branch_taken = 1'b0;
    end
end

assign branch_target = pc + imm;
```

<div class="callout note"><span class="title">How the ALU drives the comparison</span>
The ALU computes both signed and unsigned <code>SLT</code>-style results; bit 0 of the result holds the comparison outcome. <code>BLT</code>/<code>BGE</code> read the signed bit, <code>BLTU</code>/<code>BGEU</code> read the unsigned one, and <code>BEQ</code>/<code>BNE</code> read the ALU's zero flag. The branch resolution block just routes the appropriate signal into <code>branch_taken</code>.
</div>

<div class="pipeline-arrow"></div>

## Memory Access (MEM) {#memory}

Implemented in [`src/mem_stage.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/mem_stage.sv). MEM presents the ALU result as an address to the data memory and either drives a word in (for stores) or latches a word out (for loads).

<div class="img-wrapper">
  <img src="{{ '/images/stage_mem.svg' | relative_url }}" alt="MEM stage block diagram: data memory interface, byte-enable generation, and sub-word sign/zero-extension">
  <span class="caption">Figure 5: MEM stage. The byte-enable function turns funct3 and the address LSBs into the mask the data memory uses to drive (stores) or select (loads) the right bytes.</span>
</div>

### Byte enables for sub-word access

RV32I has byte and half-word loads and stores in addition to the natural word-aligned ones. The data memory is word-addressed under the hood, so the MEM stage produces a 4-bit byte-enable mask that picks which bytes of the addressed word participate in the transaction. The mask depends on `funct3` (which sub-word size) and the low two bits of the address (which byte or half-word within the word).

```verilog
function automatic logic [3:0] get_byte_enable(logic [2:0] funct3, logic [1:0] addr_lsb);
    case (funct3)
        F3_BYTE: begin : ByteEnable
            case (addr_lsb)
                2'b00: return 4'b0001;
                2'b01: return 4'b0010;
                2'b10: return 4'b0100;
                2'b11: return 4'b1000;
            endcase
        end
        F3_HALF: begin : HalfwordEnable
            case (addr_lsb[1])
                1'b0: return 4'b0011;   // Lower halfword
                1'b1: return 4'b1100;   // Upper halfword
            endcase
        end
        default: return 4'b1111;        // Word access
    endcase
endfunction

assign dmem_be = get_byte_enable(ex_mem_funct3, ex_mem_alu_result[1:0]);
```

The data memory ([`src/data_memory.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/data_memory.sv)) consumes `dmem_be` as its byte-enable per cell. Sign-extension (for `LB`/`LH`) vs. zero-extension (for `LBU`/`LHU`) is handled on the read-data path by selecting between sign-extended and zero-extended views of the addressed bytes before the value propagates to the MEM/WB register.

<div class="pipeline-arrow"></div>

## Writeback (WB) {#writeback}

Implemented in [`src/wb_stage.sv`](https://github.com/cshieldsce/riscv-5i/blob/main/src/wb_stage.sv). WB picks which value lands in the destination register using `wb_mux_sel`.

<div class="img-wrapper">
  <img src="{{ '/images/stage_wb.svg' | relative_url }}" alt="WB stage block diagram: three-way result multiplexer selecting between ALU result, loaded data, and PC+4">
  <span class="caption">Figure 6: WB stage. The three-way mux on the right selects which value goes into the register file.</span>
</div>

`wb_mux_sel` has three encodings:

| Encoding | Source | Used by |
|---|---|---|
| `2'b00` | ALU result | R-type, I-type ALU, LUI, AUIPC |
| `2'b01` | Data loaded from memory | LB, LH, LW, LBU, LHU |
| `2'b10` | `PC + 4` | JAL, JALR (return address) |

The first two are obvious. The third is what makes function calls possible: `JAL ra, target` puts `PC + 4` into `ra` (`x1`), so `ret` (which is `JALR x0, 0(ra)`) jumps back to the instruction after the call.

<div class="callout note"><span class="title">Why PC+4 instead of PC</span>
<em>RISC-V Unprivileged ISA Specification</em>, Section 2.5 ("Control Transfer Instructions"). JAL and JALR save the address of the instruction <em>after</em> the call so the callee can return without any further offset arithmetic. Saving PC instead of PC+4 would force every return to add 4, which the ISA designers (rightly) decided was the caller's job once, not the callee's job every time.
</div>

<div class="pipeline-arrow"></div>

## What each pipeline register carries {#summary}

Each pipeline register hands a bundle of architectural state and control signals to the next stage. The fields fall out from what that stage's logic still needs to consume.

| Register | Data fields | Control signals | Why |
|---|---|---|---|
| **IF/ID** | `pc`, `instruction`, `pc+4` | n/a; generated in ID | Hand the fetched word and its address to the decoder |
| **ID/EX** | `pc`, `pc+4`, `rs1_data`, `rs2_data`, `imm`, `rs1`, `rs2`, `rd`, `funct3` | `reg_write`, `mem_write`, `alu_control`, `op_a_sel`, `op_b_sel`, `wb_mux_sel`, branch, jump, jalr | Operands and full control bundle for execute |
| **EX/MEM** | `alu_result`, `rs2_data`, `rd`, `pc+4`, `funct3`, `rs2` | `reg_write`, `mem_write`, `wb_mux_sel` | Address and store-data for memory; preserve writeback target |
| **MEM/WB** | `mem_read_data`, `alu_result`, `rd`, `pc+4` | `reg_write`, `wb_mux_sel` | Three writeback sources plus the destination register |

<div class="callout note"><span class="title">Why <code>rs2</code> rides in EX/MEM</span>
Carrying the source register index <code>rs2</code> through to EX/MEM enables store-data forwarding: if a store's data operand is being produced by an instruction one cycle ahead in the pipeline, the forwarding unit can route the fresher value into the store path. See <a href="{{ '/architecture/hazards/' | relative_url }}#case3">Hazards Case 3</a>. Textbook diagrams often omit this; it costs a few extra bits in the register but avoids a real correctness bug.
</div>

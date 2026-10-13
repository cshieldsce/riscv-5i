OUTPUT_ARCH( "riscv" )
ENTRY(rvtest_entry_point)

/* Code at 0, data and signature at 0x200000 and tohost at 0x80001000, which
   is the memory map the core and the RISCOF plugin already use */
SECTIONS
{
  . = 0x00000000;
  .text : { *(.text.init) *(.text) }

  . = 0x00200000;
  .data : { *(.data) *(.data.string) }
  .bss : { *(.bss) }

  . = 0x80001000;
  .tohost : { *(.tohost) }

  _end = .;
}

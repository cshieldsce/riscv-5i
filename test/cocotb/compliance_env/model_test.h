// model_test.h: riscv-arch-test 3.9.1 target macros for the cocotb compliance run.
// Based on test/verification/compliance/model_test.h, with RVMODEL_BOOT empty
// because 3.9.1 tests define the entry label themselves.
#ifndef _COMPLIANCE_MODEL_H
#define _COMPLIANCE_MODEL_H

#define RVMODEL_DATA_SECTION                                                  \
        .pushsection .tohost,"aw",@progbits;                                  \
        .align 8; .global tohost; tohost: .dword 0;                           \
        .align 8; .global fromhost; fromhost: .dword 0;                       \
        .popsection;

// A store to tohost ends the simulation
#define RVMODEL_HALT                                                          \
  li x1, 1;                                                                   \
  write_tohost:                                                               \
    sw x1, tohost, t5;                                                        \
    j write_tohost;

#define RVMODEL_BOOT

#define RVMODEL_DATA_BEGIN                                                    \
  RVMODEL_DATA_SECTION                                                        \
  .align 4;                                                                   \
  .global begin_signature; begin_signature:

#define RVMODEL_DATA_END                                                      \
  .align 4;                                                                   \
  .global end_signature; end_signature:

#define RVMODEL_IO_INIT
#define RVMODEL_IO_WRITE_STR(_R, _STR)
#define RVMODEL_IO_CHECK()
#define RVMODEL_IO_ASSERT_GPR_EQ(_S, _R, _I)
#define RVMODEL_IO_ASSERT_SFPR_EQ(_F, _R, _I)
#define RVMODEL_IO_ASSERT_DFPR_EQ(_D, _R, _I)

#define RVMODEL_SET_MSW_INT
#define RVMODEL_CLEAR_MSW_INT
#define RVMODEL_CLEAR_MTIMER_INT
#define RVMODEL_CLEAR_MEXT_INT

#endif // _COMPLIANCE_MODEL_H

#!/usr/bin/env python3

import json
import multiprocessing
import os

from z3 import *

from md32_dis import disassemble_dword, parse_args


def process_dword(dword):
    disassembled = disassemble_dword(dword)
    if disassembled is None:
        return None

    instr, instr_size, mnemonic, args = disassembled

    if instr_size > 2:
        # We're not testing 32-bit instructions.
        #print("Not testing {}.".format(mnemonic))
        return None

    args = parse_args(args)
    argfmt = None
    if args:
        argfmt = type(args).__name__
    if not argfmt:
        raise ValueError("Unknown argument format: \"{}\"".format(args))

    return (instr, mnemonic, argfmt)

def main():
    opcodes = set()

    processes = os.cpu_count()
    chunk_size = 16

    with multiprocessing.Pool(processes) as pool:
        print("Generating candidates...")
        candidates = pool.imap_unordered(process_dword, range(0x8000 << 16, 1 << 32, 1 << 16), chunk_size)

        instruction_map = dict()
        for instr, mnemonic, argfmt in filter(lambda x: x != None, candidates):
            if instruction_map.get((mnemonic, argfmt)) is None:
                instruction_map[(mnemonic, argfmt)] = set()
            instruction_map[(mnemonic, argfmt)].add(instr)

        for (mnemonic, argfmt), instrs in instruction_map.items():
            instr = BitVec("instr", 32)

            actual = []
            for i in instrs:
                actual.append(instr == BitVecVal(i, 32))
            actual = Or(actual)

            model = []
            model.append((instr & 0x0000ffff) == BitVecVal(0, 32))
            model.append(ULE(instr, max(instrs)))
            model.append(UGE(instr, min(instrs)))
            model = And(model)

            #print("{} ({}): {}".format(mnemonic, argfmt, simplify(actual)))
            print("{} ({}): {}".format(mnemonic, argfmt, simplify(model)))

            s = Solver()
            s.add(Not(actual == model))
            if s.check() == sat:
                print("Error: Model does not match reality. Counterexample: instr = 0x{:08x}".format(s.model()[instr].as_long()))
                continue

            opcodes.add((mnemonic, argfmt, min(instrs), max(instrs)))

    opcodes_file = open('opcodes-16-brute.json', 'w')
    json.dump(list(opcodes), opcodes_file)
    opcodes_file.close()

    print("Done!")


if __name__ == "__main__":
    main()

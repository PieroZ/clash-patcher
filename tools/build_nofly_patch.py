"""Zrodlo asemblerowe poprawki "naziemne nie dolaczaja do latajacych" (CodePatch no_ground_on_fly).

Uruchomienie wypisuje bajty dla obu wersji gry; wynik jest wklejony do clash_exe_patches.py.
Wymaga: pip install keystone-engine
"""
from keystone import Ks, KS_ARCH_X86, KS_MODE_32
ks = Ks(KS_ARCH_X86, KS_MODE_32)
def asm(src, addr):
    enc, _ = ks.asm(src, addr)
    return bytes(enc)

# ---- terrain-cost routine:  eax=army, edx=x, ebx=y  ->  eax = movement cost (0 = impassable)
def tc_dos(a):
    pre = """push ecx; push edx; push ebx; push esi; push edi; push ebp
    sub esp, 0x60
    mov esi, edx
    mov edi, ebx
    mov edx, eax
    mov eax, esp
    call 0x29e22
    call 0"""
    L1 = a + len(asm(pre, a))
    d = lambda t: f"{t - L1:#x}" if t >= L1 else f"-{L1 - t:#x}"
    # globals read through the (relocated) operands of existing instructions
    # 0x2ac03 -> &game_ptr, 0x2ac31 -> &special_flag, 0x2ac45 -> class_table
    return f"""
    push ecx; push edx; push ebx; push esi; push edi; push ebp
    sub esp, 0x60
    mov esi, edx
    mov edi, ebx
    mov edx, eax
    mov eax, esp
    call 0x29e22
    call L1
L1: pop ebp
    imul eax, esi, 0x578
    imul ecx, edi, 0xe
    add eax, ecx
    mov ecx, dword ptr [ebp {d(0x2ac03)}]
    add eax, dword ptr [ecx]
    cmp word ptr [eax + 4], 0xffff
    je NOROAD
    movzx eax, byte ptr [esp + 0x1d]
    jmp DONE
NOROAD:
    movzx ecx, word ptr [eax]
    mov eax, dword ptr [ebp {d(0x2ac31)}]
    cmp dword ptr [eax], 0
    je TERR
    push ecx
    mov eax, esi
    mov edx, edi
    call 0x3cc5a
    pop ecx
    test eax, eax
    jne DONE
TERR:
    mov eax, dword ptr [ebp {d(0x2ac45)}]
    mov ecx, dword ptr [eax + ecx*4]
    movzx eax, byte ptr [esp + ecx + 0x1e]
DONE:
    add esp, 0x60
    pop ebp; pop edi; pop esi; pop ebx; pop edx; pop ecx
    ret
"""
def tc_win(a):
    return f"""
    push ecx; push edx; push ebx; push esi; push edi
    sub esp, 0x60
    mov esi, edx
    mov edi, ebx
    mov edx, eax
    mov eax, esp
    call 0x413920
    imul eax, esi, 0x578
    imul ecx, edi, 0xe
    add eax, ecx
    add eax, dword ptr [0x5202e4]
    cmp word ptr [eax + 4], 0xffff
    je NOROAD
    movzx eax, byte ptr [esp + 0x1d]
    jmp DONE
NOROAD:
    movzx ecx, word ptr [eax]
    cmp dword ptr [0x52556c], 0
    je TERR
    push ecx
    mov eax, esi
    mov edx, edi
    call 0x424370
    pop ecx
    test eax, eax
    jne DONE
TERR:
    mov ecx, dword ptr [ecx*4 + 0x52456c]
    movzx eax, byte ptr [esp + ecx + 0x1e]
DONE:
    add esp, 0x60
    pop edi; pop esi; pop ebx; pop edx; pop ecx
    ret
"""

def build(ver):
    if ver == 'dos':
        cave = 0x102420; minap = 0x258f4
        add = f"""
    cmp dword ptr [ebp - 4], 0
    jne SKIP
    push ebx
    mov eax, dword ptr [ebp - 0x18]
    movsx edx, word ptr [eax]
    movsx ebx, word ptr [eax + 2]
    mov eax, dword ptr [ebp - 0x1c]
    call TC
    pop ebx
    test eax, eax
    jne SKIP
    or eax, -1
    ret
SKIP:
    mov eax, dword ptr [ebp - 0x1c]
    jmp {minap}
"""
        move = f"""
    push ebx
    lea eax, [ebp - 0x304]
    mov edx, dword ptr [ebp - 8]
    mov ebx, dword ptr [ebp - 4]
    call TC
    pop ebx
    test eax, eax
    jne OK
    or eax, -1
    ret
OK:
    lea eax, [ebp - 0x304]
    jmp {minap}
"""
        flag = None
        tc = tc_dos
        hooks = [(0x3b447, 'add', 8), (0x3b692, 'move', 11)]
    else:
        cave = 0x4e9820; minap = 0x410010
        flag = f"""
    test ebx, ebx
    je RET
    add esp, 4
    mov eax, dword ptr [esp + 8]
    call {minap}
    jmp 0x422d24
RET:
    ret
"""
        add = f"""
    push ebx
    movsx edx, word ptr [ebp]
    movsx ebx, word ptr [ebp + 2]
    mov eax, dword ptr [esp + 0x10]
    call TC
    pop ebx
    test eax, eax
    jne SKIP
    or eax, -1
    ret
SKIP:
    mov eax, dword ptr [esp + 0xc]
    jmp {minap}
"""
        move = f"""
    push ebx
    lea eax, [esp + 8]
    mov edx, dword ptr [esp + 8 + 0x2e4]
    mov ebx, dword ptr [esp + 8 + 0x2e0]
    call TC
    pop ebx
    test eax, eax
    jne OK
    or eax, -1
    ret
OK:
    lea eax, [esp + 4]
    jmp {minap}
"""
        tc = tc_win
        hooks = [(0x422c76, 'flag', 8), (0x422d1b, 'add', 9), (0x422fc9, 'move', 7)]
    # layout: TC first, then stubs (16-byte aligned)
    parts = {}
    addr = cave
    tcb = asm(tc(addr), addr); parts['TC'] = (addr, tcb); addr += (len(tcb) + 15) & ~15
    for name, src in (('add', add), ('move', move), ('flag', flag)):
        if src is None: continue
        src = src.replace('call TC', f'call {parts["TC"][0]:#x}')
        b = asm(src, addr); parts[name] = (addr, b); addr += (len(b) + 15) & ~15
    blob = bytearray()
    for n,(a,b) in parts.items():
        off = a - cave
        blob += b'\x90' * (off - len(blob)) if False else b'\x00' * (off - len(blob))
        blob += b
    hookb = []
    for at, name, size in hooks:
        b = asm(f"call {parts[name][0]:#x}", at)
        b += b'\x90' * (size - len(b))
        hookb.append((at, b))
    return cave, bytes(blob), hookb, parts

if __name__ == '__main__':
    for v in ('dos', 'win'):
        cave, blob, hooks, parts = build(v)
        print(v, hex(cave), len(blob), {k: hex(a) for k, (a, b) in parts.items()})
        print(blob.hex())
        for at, b in hooks: print(' hook', hex(at), b.hex())

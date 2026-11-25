"""Перевірка стартових номіналів RF-тракту LoRa-пейджера на 433 МГц (ідеальні елементи)."""
import cmath, math
f0 = 433.92e6
def zl(L, f): return 1j*2*math.pi*f*L
def zc(C, f): return 1/(1j*2*math.pi*f*C)
def par(a, b): return a*b/(a+b)
def tx_chain(f, L3, C17, notch_C=None):
    # навантаження: вхід ключа 50 Ом, назад до RFO
    z = 50 + zc(100e-12, f)                    # C20 розділовий
    z = par(z, zc(6.8e-12, f))                 # C19
    z = z + zl(22e-9, f)                       # L5
    z = par(z, zc(12e-12, f))                  # C18
    z = z + zl(22e-9, f)                       # L4
    z = par(z, zc(C17, f))                     # C17 (фільтр + узгодження)
    zs = zl(L3, f) if notch_C is None else par(zl(L3, f), zc(notch_C, f))
    z = z + zs                                 # L3 (|| C29)
    return par(z, zl(47e-9, f))                # L2 47 нГн на VR_PA
def gain_db(f, L3, C17, notch_C=None, Rs=12.0):
    """Передача потужності від джерела Rs (≈ Zopt PA) у 50 Ом на виході, дБ."""
    # ABCD-метод
    def ser(Z): return [[1, Z], [0, 1]]
    def sh(Z): return [[1, 0], [1/Z, 1]]
    def mul(a, b): return [[a[0][0]*b[0][0]+a[0][1]*b[1][0], a[0][0]*b[0][1]+a[0][1]*b[1][1]],
                           [a[1][0]*b[0][0]+a[1][1]*b[1][0], a[1][0]*b[0][1]+a[1][1]*b[1][1]]]
    zs = zl(L3, f) if notch_C is None else par(zl(L3, f), zc(notch_C, f))
    M = sh(zl(47e-9, f))
    for e in (ser(zs), sh(zc(C17, f)), ser(zl(22e-9, f)), sh(zc(12e-12, f)), ser(zl(22e-9, f)),
              sh(zc(6.8e-12, f)), ser(zc(100e-12, f))):
        M = mul(M, e)
    A, B, C, D = M[0][0], M[0][1], M[1][0], M[1][1]
    RL = 50
    s21 = 2*math.sqrt(Rs*RL)/(A*RL + B + C*Rs*RL + D*Rs)
    return 20*math.log10(abs(s21))
for name, L3, C17, C29 in (("без режектора", 10e-9, 18e-12, None),
                           ("з режектором", 6.8e-9, 18e-12, 4.7e-12),
                           ("було (L3=TBD≈0, C17=6.8p)", 1e-12, 6.8e-12, None)):
    z = tx_chain(f0, L3, C17, C29)
    print(f"{name}: Z на RFO = {z.real:.1f} {z.imag:+.1f}j Ом; "
          f"f0 {gain_db(f0, L3, C17, C29):.1f} дБ, 2f0 {gain_db(2*f0, L3, C17, C29):.1f} дБ, "
          f"3f0 {gain_db(3*f0, L3, C17, C29):.1f} дБ")
# балун RX: ґратчастий, Rd = 74 Ом диф. (Semtech: Zopt LNA 74+j134 на 915 МГц); навантаження — по Rd/2 від кожного входу на землю
import numpy as np
Rd = 74; R0 = math.sqrt(50*Rd); w = 2*math.pi*f0
print(f"балун (формула): L = {R0/w*1e9:.1f} нГн, C = {1/(w*R0)*1e12:.2f} пФ")
L, C = 22e-9, 6.2e-12
ys, yl, yP, yN, yh = 1j*w*C, 1/(1j*w*L), 1/(1j*w*L), 1j*w*C, 2/Rd
G = np.array([[ys+yl, -ys, -yl], [-ys, ys+yP+yh, 0], [-yl, 0, yl+yN+yh]])
v = np.linalg.solve(G, np.array([1, 0, 0], complex)); z = v[0]; g = (z-50)/(z+50)
print(f"балун 22 нГн / 6,2 пФ: Zвх = {z.real:.1f} {z.imag:+.1f}j Ом, S11 = {20*math.log10(abs(g)):.1f} дБ, "
      f"|VP|/|VN| = {abs(v[1])/abs(v[2]):.2f}, зсув фаз = {abs(math.degrees(cmath.phase(v[1]/v[2]))):.0f}°")

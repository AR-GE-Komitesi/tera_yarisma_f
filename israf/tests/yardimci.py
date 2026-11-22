"""Testler için küçük, elle hesaplanabilir veri seti."""
from israf.aktarim import import_csv
from israf.models import ImportBatch

DISHES_CSV = """yemek_kodu,yemek_adi,kategori,tur
mercimek,Mercimek Çorbası,corba,bakliyat çorbası
tavuk,Tavuk Sote,ana_yemek,tavuk
kofte,Izgara Köfte,ana_yemek,kırmızı et
pilav,Pirinç Pilavı,yan_yemek,pilav
makarna,Makarna,yan_yemek,makarna
salata,Mevsim Salata,salata,yeşillik
ayran,Ayran,icecek,içecek
"""

# 20.11: tavuk 12:30'da tükendi, köfte artmış.
PRODUCTION_CSV = """tarih,ogun,yemek_kodu,uretilen_porsiyon,artan_porsiyon,bitis_saati
2026-11-20,ogle,mercimek,10,1,
2026-11-20,ogle,tavuk,6,0,12:30
2026-11-20,ogle,kofte,6,2,
2026-11-20,ogle,pilav,5,1,
2026-11-20,ogle,makarna,5,0,13:15
"""

# Her tepside çorba + ana + yan. 9 tepsi.
TRAYS_CSV = """tarih,ogun,tepsi_id,yemek_kodu,durum
2026-11-20,ogle,T1,mercimek,bitti
2026-11-20,ogle,T1,tavuk,bitti
2026-11-20,ogle,T1,pilav,bitti
2026-11-20,ogle,T2,mercimek,bitti
2026-11-20,ogle,T2,tavuk,bitti
2026-11-20,ogle,T2,makarna,yarim
2026-11-20,ogle,T3,mercimek,yarim
2026-11-20,ogle,T3,tavuk,bitti
2026-11-20,ogle,T3,makarna,bitti
2026-11-20,ogle,T4,mercimek,dokunulmadi
2026-11-20,ogle,T4,tavuk,yarim
2026-11-20,ogle,T4,pilav,bitti
2026-11-20,ogle,T5,mercimek,bitti
2026-11-20,ogle,T5,tavuk,bitti
2026-11-20,ogle,T5,makarna,bitti
2026-11-20,ogle,T6,mercimek,bitti
2026-11-20,ogle,T6,tavuk,dokunulmadi
2026-11-20,ogle,T6,pilav,yarim
2026-11-20,ogle,T7,mercimek,bitti
2026-11-20,ogle,T7,kofte,bitti
2026-11-20,ogle,T7,makarna,bitti
2026-11-20,ogle,T8,mercimek,belirsiz
2026-11-20,ogle,T8,kofte,dokunulmadi
2026-11-20,ogle,T8,pilav,bitti
2026-11-20,ogle,T9,mercimek,bitti
2026-11-20,ogle,T9,kofte,yarim
2026-11-20,ogle,T9,makarna,dokunulmadi
"""


def load(kind, text, name="dosya.csv", encoding="utf-8", replace=False):
    return import_csv(kind, text.encode(encoding), name, replace=replace)


def load_fixture():
    for kind, text in (
        (ImportBatch.Kind.DISHES, DISHES_CSV),
        (ImportBatch.Kind.PRODUCTION, PRODUCTION_CSV),
        (ImportBatch.Kind.TRAYS, TRAYS_CSV),
    ):
        batch = load(kind, text)
        assert batch.status == ImportBatch.Status.OK, batch.messages

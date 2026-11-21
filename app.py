import uuid
import streamlit as st
from supabase import create_client, Client

# --- CSALÁDTAGOK LISTÁJA (írd át nyugodtan) ---
CSALADTAGOK = ["Anya", "Apa", "Dodó", "Viki", "Bella","Kopi","Patrik","Mama","Sonny"]

st.set_page_config(page_title="Karácsonyi Kívánságlista", page_icon="🎄", layout="wide")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

if "uzenet" in st.session_state:
    st.toast(st.session_state.pop("uzenet"))

# --- BELÉPÉS (regisztráció nélkül, közös PIN-nel) ---
if not st.session_state.get("belepve"):
    st.title("Karácsonyi Kívánságlista")
    st.write("Válaszd ki a neved, és írd be a családi kódot a belépéshez.")

    with st.form("belepes_form"):
        nev = st.selectbox("Ki vagy?", CSALADTAGOK)
        pin = st.text_input("Családi PIN-kód", type="password")
        if st.form_submit_button("Belépés", type="primary"):
            if pin == str(st.secrets["CSALADI_PIN"]):
                st.session_state["belepve"] = True
                st.session_state["en_vagyok"] = nev
                st.rerun()
            else:
                st.error("Hibás PIN-kód!")
    st.stop()

en_vagyok = st.session_state["en_vagyok"]

# --- FEJLÉC ---
col_cim, col_ki = st.columns([4, 1])
with col_cim:
    st.title("Karácsonyi Kívánságlista")
    st.caption(f"Belépve mint: **{en_vagyok}** — a saját kívánságaidnál a foglalás rejtve marad.")
with col_ki:
    st.write("")
    if st.button("Névváltás / Kilépés"):
        st.session_state.clear()
        st.rerun()

tab_lista, tab_uj = st.tabs(["Ajándéklista", "Új kívánság hozzáadása"])

# --- 1. FÜL: GALÉRIA ---
with tab_lista:
    szuro = st.selectbox("Szűrés személyre", ["Mindenki"] + CSALADTAGOK)

    query = supabase.table("ajandekok").select("*").order("created_at", desc=True)
    if szuro != "Mindenki":
        query = query.eq("ki_keri", szuro)
    ajandekok = query.execute().data

    if not ajandekok:
        st.info("Még nincs felvett ajándék ebben a nézetben.")
    else:
        oszlopok = st.columns(2)
        for idx, item in enumerate(ajandekok):
            with oszlopok[idx % 2]:
                with st.container(border=True):
                    if item.get("kep_url"):
                        try:
                            st.image(item["kep_url"], use_container_width=True)
                        except Exception:
                            pass

                    st.subheader(item["termek"])

                    meta = f"**Kéri:** {item['ki_keri']}"
                    if item.get("ar"):
                        meta += f"  |  **Kb. ár:** {item['ar']}"
                    st.write(meta)

                    if item.get("link"):
                        url = item["link"].strip()
                        if not url.startswith(("http://", "https://")):
                            url = "https://" + url
                        st.link_button("Megnézem a webshopban", url)

                    st.divider()

                    # Spoiler-védelem: a saját listádon nem látod, mi van lefoglalva
                    if item["ki_keri"] == en_vagyok:
                        c1, c2 = st.columns([3, 1])
                        c1.caption("Saját kívánságod (foglalás rejtve)")
                        if c2.button("Törlés", key=f"torol_{item['id']}"):
                            supabase.table("ajandekok").delete().eq("id", item["id"]).execute()
                            st.session_state["uzenet"] = "Kívánság törölve."
                            st.rerun()
                    else:
                        if not item["lefoglalva"]:
                            if st.button("Lefoglalom", key=f"foglal_{item['id']}", type="primary"):
                                supabase.table("ajandekok").update({
                                    "lefoglalva": True,
                                    "ki_foglalta": en_vagyok
                                }).eq("id", item["id"]).execute()
                                st.session_state["uzenet"] = f"Lefoglalva: {item['termek']}"
                                st.rerun()
                        else:
                            foglalo = item.get("ki_foglalta") or "Valaki"
                            st.success(f"Lefoglalva ({foglalo})")
                            if foglalo == en_vagyok:
                                if st.button("Foglalás visszavonása", key=f"vissza_{item['id']}"):
                                    supabase.table("ajandekok").update({
                                        "lefoglalva": False,
                                        "ki_foglalta": None
                                    }).eq("id", item["id"]).execute()
                                    st.session_state["uzenet"] = "Foglalás visszavonva."
                                    st.rerun()

# --- 2. FÜL: ÚJ KÍVÁNSÁG ---
with tab_uj:
    with st.form("uj_ajandek_form", clear_on_submit=True):
        ki_keri = st.selectbox("Kinek a kívánsága?", CSALADTAGOK, index=CSALADTAGOK.index(en_vagyok))
        termek = st.text_input("Termék neve *", placeholder="pl. LEGO szett vagy bőr pénztárca")
        ar = st.text_input("Kb. ár (opcionális)", placeholder="pl. 15 000 Ft")
        link = st.text_input("Webshop link (opcionális)", placeholder="https://...")
        feltoltott_kep = st.file_uploader("Kép feltöltése telefonról/gépről (opcionális)", type=["png", "jpg", "jpeg", "webp"])
        kep_link = st.text_input("Vagy kép közvetlen linkje (opcionális)")

        if st.form_submit_button("Hozzáadás a listához", type="primary"):
            if not termek.strip():
                st.error("A termék nevét kötelező megadni!")
            else:
                vegso_kep_url = kep_link.strip() or None

                if feltoltott_kep is not None:
                    ext = feltoltott_kep.name.rsplit(".", 1)[-1].lower()
                    fajlnev = f"{uuid.uuid4()}.{ext}"
                    supabase.storage.from_("kepek").upload(
                        path=fajlnev,
                        file=feltoltott_kep.getvalue(),
                        file_options={"content-type": feltoltott_kep.type}
                    )
                    vegso_kep_url = supabase.storage.from_("kepek").get_public_url(fajlnev)

                supabase.table("ajandekok").insert({
                    "termek": termek.strip(),
                    "ki_keri": ki_keri,
                    "ar": ar.strip() or None,
                    "link": link.strip() or None,
                    "kep_url": vegso_kep_url,
                    "lefoglalva": False
                }).execute()

                st.session_state["uzenet"] = "Kívánság sikeresen hozzáadva!"
                st.rerun()

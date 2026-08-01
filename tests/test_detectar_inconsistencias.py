"""Pruebas de scripts/detectar_inconsistencias.py.

Reproduce el hallazgo real (31-07-2026) que motivo este script: el
incendio del CCCT y el incendio del C.C. Los Cedros en Porlamar se
publicaron 2 veces cada uno, sin que ninguna verificacion automatica lo
señalara -- este script es la red explicita que faltaba.
"""

from detectar_inconsistencias import (
    detectar_fuentes_muertas_en_informes,
    detectar_posibles_duplicados,
)


def _alerta(tipo, titulo, clave, fecha_evento, fecha_temprana, municipio, fuentes):
    return {
        "tipo": tipo, "titulo": titulo, "clave_dedup": clave,
        "fecha_evento": fecha_evento, "fecha_evento_temprana": fecha_temprana,
        "municipio": municipio,
        "fuentes": [{"nombre": n, "link": l} for n, l in fuentes],
    }


def test_ccct_duplicado_se_detecta_por_token_compartido_del_link():
    # Caso real: dos clusters del mismo incendio del CCCT, ninguno con
    # municipio en comun (uno None, el otro con "Libertador" alucinado) --
    # solo el token "ccct", presente en ambos links, los delata.
    a = _alerta(
        "incendio", "Incendio en Distrito Capital", "incendio::Distrito Capital::2026-07-30",
        "2026-07-30T19:07:44+00:00", "2026-07-30T14:46:56+00:00", None,
        [("Noticias de Aqui", "https://noticiasdeaqui.co/2026/07/30/reportan-incendio-en-el-ccct-en-caracas/"),
         ("La Verdad", "https://laverdad.com/reportan-5-personas-afectadas-tras-el-incendio-en-una-libreria-del-ccct/")],
    )
    b = _alerta(
        "incendio", "Incendio en Parroquia La Vega, Municipio Libertador, Distrito Capital",
        "incendio::Distrito Capital::2026-07-31",
        "2026-07-31T12:57:13+00:00", "2026-07-31T12:57:13+00:00", "Libertador",
        [("Reporte Confidencial", "https://reporteconfidencial.info/2026/07/31/ccct/")],
    )
    resultado = detectar_posibles_duplicados([a, b])
    assert len(resultado) == 1
    assert "ccct" in resultado[0][2]


def test_los_cedros_duplicado_se_detecta_por_mismo_municipio():
    # Caso real: el segundo cluster (Porlamar) no comparte ningun token de
    # link con el primero (Isla de Margarita) -- solo coincidir en
    # municipio ("Mariño", una vez que classify.py lo detecta via el alias
    # "Porlamar") permite verlos como el mismo evento.
    a = _alerta(
        "incendio", "Incendio en Municipio Mariño, Nueva Esparta", "incendio::Nueva Esparta::2026-07-30",
        "2026-07-30T13:32:48+00:00", "2026-07-30T12:12:15+00:00", "Mariño",
        [("La Prensa de Monagas", "https://laprensademonagas.com/voraz-incendio-consume-reconocido-centro-comercial-en-la-isla-de-margarita-video/")],
    )
    b = _alerta(
        "incendio", "Incendio en Nueva Esparta", "incendio::Nueva Esparta::2026-07-31",
        "2026-07-31T14:33:37+00:00", "2026-07-31T14:10:11+00:00", "Mariño",
        [("Reporte Confidencial", "https://reporteconfidencial.info/2026/07/31/incendio-en-porlamar/")],
    )
    resultado = detectar_posibles_duplicados([a, b])
    assert len(resultado) == 1
    assert "municipio" in resultado[0][2]


def test_eventos_distintos_de_estados_distintos_no_se_marcan():
    # Caso de control: dos inundaciones reales, en estados distintos, sin
    # municipio en comun, no deben marcarse solo por compartir vocabulario
    # generico de prensa ("lluvias", "sectores", "provocaron"...).
    a = _alerta(
        "inundacion", "Inundación en Sucre", "inundacion::Sucre::2026-07-29",
        "2026-07-29T02:46:02+00:00", "2026-07-29T02:46:02+00:00", None,
        [("El Tiempo", "https://eltiempove.com/fuertes-lluvias-provocaron-inundaciones-y-fallas-electricas-en-varios-sectores-de-cumana/")],
    )
    b = _alerta(
        "inundacion", "Inundación en Zulia", "inundacion::Zulia::2026-07-27",
        "2026-07-27T12:26:20+00:00", "2026-07-27T12:26:20+00:00", None,
        [("Diario La Nacion", "https://lanacionweb.com/lluvias-torrenciales-provocaron-inundaciones-severas-en-el-zulia/")],
    )
    assert detectar_posibles_duplicados([a, b]) == []


def test_mismo_tipo_fuera_de_la_ventana_de_tiempo_no_se_marca():
    a = _alerta(
        "incendio", "Incendio en Distrito Capital", "incendio::Distrito Capital::2026-07-10",
        "2026-07-10T10:00:00+00:00", "2026-07-10T10:00:00+00:00", None,
        [("Fuente", "https://ejemplo.com/incendio-en-el-ccct/")],
    )
    b = _alerta(
        "incendio", "Incendio en Distrito Capital", "incendio::Distrito Capital::2026-07-31",
        "2026-07-31T10:00:00+00:00", "2026-07-31T10:00:00+00:00", None,
        [("Fuente", "https://ejemplo.com/incendio-en-el-ccct/")],
    )
    assert detectar_posibles_duplicados([a, b]) == []


def test_tipos_distintos_no_se_comparan():
    a = _alerta(
        "incendio", "Incendio en Distrito Capital", "incendio::Distrito Capital::2026-07-30",
        "2026-07-30T10:00:00+00:00", "2026-07-30T10:00:00+00:00", "Chacao",
        [("Fuente", "https://ejemplo.com/incendio-en-el-ccct/")],
    )
    b = _alerta(
        "inundacion", "Inundación en Miranda", "inundacion::Miranda::2026-07-30",
        "2026-07-30T11:00:00+00:00", "2026-07-30T11:00:00+00:00", "Chacao",
        [("Fuente", "https://ejemplo.com/inundacion-en-el-ccct/")],
    )
    assert detectar_posibles_duplicados([a, b]) == []


def test_correos_institucionales_no_generan_falsos_positivos_por_link():
    # Los links de reportes de filial son una busqueda de Gmail por id de
    # mensaje (ver attachments_filial.py) -- dos reportes de filial
    # DISTINTOS podrian compartir tokens del id de busqueda sin ser el
    # mismo evento en absoluto.
    a = _alerta(
        "crisis_migratoria", "Reporte de personas desplazadas", "crisis_migratoria::Anzoategui::2026-07-29",
        "2026-07-29T17:55:40+00:00", "2026-07-29T17:55:40+00:00", "Piritu",
        [("Reporte de filial", "https://mail.google.com/mail/u/0/#search/rfc822msgid:DM8PR08MB741418361C69B8A5633E6725A5CA2@DM8PR08MB7414.namprd08.prod.outlook.com")],
    )
    b = _alerta(
        "crisis_migratoria", "Reporte de personas desplazadas", "crisis_migratoria::Apure::2026-07-29",
        "2026-07-29T16:18:23+00:00", "2026-07-29T16:18:23+00:00", None,
        [("Reporte de filial", "https://mail.google.com/mail/u/0/#search/rfc822msgid:DM8PR08MB741497BA10F0F19591EE7617A5CA2@DM8PR08MB7414.namprd08.prod.outlook.com")],
    )
    assert detectar_posibles_duplicados([a, b]) == []


def test_fuentes_muertas_se_detectan_contra_historico(tmp_path, monkeypatch):
    historico = tmp_path / "historico_fuentes_texto.jsonl"
    historico.write_text(
        '{"tipo": "incendio", "ubicacion": "Miranda", "fuentes": '
        '[{"nombre": "Noticias de Aqui", "link": "https://ejemplo.com/vivo/"}]}\n',
        encoding="utf-8",
    )
    informes_dir = tmp_path / "informes"
    informes_dir.mkdir()
    (informes_dir / "2026-07_incendio.json").write_text(
        '{"fuentes": [{"nombre": "Noticias de Aqui", "link": "https://ejemplo.com/vivo/"}, '
        '{"nombre": "El Tiempo", "link": "https://ejemplo.com/muerto/"}]}',
        encoding="utf-8",
    )

    import detectar_inconsistencias as di
    monkeypatch.setattr(di, "HISTORICO_FUENTES_PATH", str(historico))
    monkeypatch.setattr(di, "INFORMES_GLOB", str(informes_dir / "*.json"))

    resultado = detectar_fuentes_muertas_en_informes()
    ruta = str(informes_dir / "2026-07_incendio.json")
    assert len(resultado) == 1
    fuentes_muertas = next(iter(resultado.values()))
    assert [f["link"] for f in fuentes_muertas] == ["https://ejemplo.com/muerto/"]

# WeSleep — L'Alarma Intel·ligent i Assistent de Son Preventiu

> **Transformant dades de wearables en prevenció de salut real.**

WeSleep és una solució dissenyada per a **mútues de salut i proveïdors d'assegurances**. Transforma les dades en brut dels wearables dels pacients en una eina de prevenció de salut i millora del benestar diari, actuant com un pont entre la tecnologia de consum i l'atenció mèdica professional.

---

## 🎯 Visió

El son no és només descans; és el **biomarcador més precís de la salut general d'un individu**. WeSleep no busca substituir el consell mèdic, sinó apoderar l'usuari amb intel·ligència artificial perquè prengui el control del seu descans i s'avanci a possibles problemes de salut **abans que esdevinguin crònics**.

---

## ✨ Funcionalitats Principals

### 1. Despertador Intel·ligent Predictiu (Smart Alarm)

El nucli de WeSleep és garantir que l'usuari es desperti amb la **màxima energia possible**, evitant la inèrcia del son (despertar en fase de son profund).

**Com funciona:**

Atès que els wearables no transmeten dades en temps real durant la nit, WeSleep utilitza un **motor predictiu basat en l'històric de l'usuari**.

- **La Finestra de Despertar:** Si l'usuari configura l'alarma a les 7:30 AM, el sistema obre una finestra intel·ligent de 30 minuts (de 7:00 a 7:30 AM).
- L'algorisme analitza els patrons de les nits anteriors i calcula el moment estadísticament més probable en què l'usuari estarà en una fase de **son lleuger** (p. ex., a les 7:20 AM), programant l'alarma per a aquest instant precís.

---

### 2. Motor d'Anàlisi Preventiu (Sense Diagnòstics)

Utilitzem **Intel·ligència Artificial Avançada (LLMs)** per analitzar tendències a llarg termini en mètriques clau:

| Mètrica | Descripció |
|---|---|
| Variabilitat de la Freqüència Cardíaca (VFC) | Indicador de recuperació i estrès del sistema nerviós |
| Fases del son | Distribució de son lleuger, profund i REM |
| Oxigen en sang (SpO₂) | Detecció de possibles apnees o dessaturacions |

**Detecció de Tendències, no Malalties:**

El sistema està dissenyat amb restriccions estrictes (System Prompts) per no emetre mai cap diagnòstic mèdic. Actua exclusivament com un sistema d'alerta estructurat en dues capes analítiques de diferent impacte:

**A. Resum Setmanal (Retenció i Benestar Diari):** Una funcionalitat enfocada al pacient (User Engagement). El sistema compara les mètriques dels últims 7 dies amb la setmana anterior i genera un resum ràpid, empàtic i motivador al Dashboard web. L'objectiu és fomentar els bons hàbits amb missatges positius i de fàcil comprensió, mantenint l'usuari actiu a la plataforma.

**B. Detector d'Anomalies Mensual (Prevenció Clínica B2B):** Una funcionalitat orientada a la prevenció clínica B2B. El sistema analitza una finestra dels últims 30 dies cercant patrons de deteriorament de la salut. Per detectar una caiguda sostinguda, compara la 1a meitat del període amb la 2a meitat (tendència intra‑mes). Si s'identifica una disminució crítica (p. ex., >15% en la VFC o en l'eficiència del son), s'activa un protocol de derivació. La IA redacta una alerta formal i proactiva informant l'usuari de l'anomalia en les seves mètriques de recuperació i recomanant-li de manera contundent que programi una revisió amb un especialista de la seva mútua.
---

## 💼 Model de Negoci · B2B SaaS

WeSleep s'integra de forma transparent (**White-label**) a l'ecosistema de les mútues de salut. Oferint aquesta eina als seus assegurats, les mútues aconsegueixen:

- **Fidelització del client** — Oferint un servei de valor afegit d'ús diari (el despertador).
- **Reducció de costos mèdics** — Fomentant la prevenció. Un usuari que acudeix al metge de manera primerenca gràcies a un avís de WeSleep evita tractaments reactius molt més costosos en el futur.

---



## 📚 Documentació tècnica

Per una descripció 100% tècnica del backend (arquitectura, model multi‑tenant, endpoints, fluxos, DB i testing), consulta:

- [README Tècnic](README_TECHNICAL.md)


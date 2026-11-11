# IMDB atsiliepimų nuotaikos klasifikatorius: reikalavimai

**Versija:** 1.6
**Data:** 2026-11-11
**Autorius:** Nojus (nojusbuc)

## 1. Apimtis

**Problema.** Pagal filmo atsiliepimo tekstą nustatyti, ar jis teigiamas, ar neigiamas (dvejetainė klasifikacija).
Vertinamas ne modelio SOTA, o atkartojamas srautas aplink jį: DVC pipeline'as, klasterio MLflow, Docker vaizdas.

**U2 papildymas.** Mokymas su HPO (Optuna, įdėtiniai run'ai), MLflow Model Registry su alias'u `@champion`,
FastAPI inferencijos servisas tame pačiame kind klasteryje, CI (GitHub Actions) ir CD su kokybės vartu ir rollback.
Servisas modelį ima tik iš registro pagal alias'ą; vaizde modelio nėra.

**Duomenys.** Hugging Face `stanfordnlp/imdb`, fiksuota revizija `e6281661ce1c48d982bc483cf8a173c1bbeb5d31`
(Large Movie Review Dataset, Maas et al., 2011). Naudojami `train` ir `test` failai: 50 000 atsiliepimų su žymomis,
klasės subalansuotos 50/50. 418 atsiliepimų pasikartoja (prieštaringų žymų nėra), todėl jie pašalinami prieš padalijimą,
kad tas pats tekstas nepatektų ir į mokymo, ir į testinę imtį. Lieka 49 582; stratifikuotas padalijimas 80/20
(`params.yaml` `prepare`): 39 664 mokymui, 9 917 testui, abiejose 50,2 % teigiamų.

**Modelis.** TF-IDF (žodžiai ir bigramos) + logistinė regresija, mokoma CPU per sekundes.
Klasės subalansuotos, todėl pagrindinė metrika yra **accuracy**, papildomai F1. Atsitiktinio spėjimo bazė 0,50.
Hiperparametrai (`C` 20,5, `max_features` 50 000, `ngram_max` 2) parinkti Optuna paieška.

## 2. Funkciniai reikalavimai

| ID | Reikalavimas | Prioritetas |
| --- | --- | --- |
| FR-01 | Modelis pagal atsiliepimo tekstą grąžina klasę: 1 (teigiamas) arba 0 (neigiamas) | Must |
| FR-02 | `dvc.yaml` pipeline'as `prepare → train → evaluate` iš DVC versijuotų duomenų sukuria modelį ir `metrics.json` | Must |
| FR-03 | Kiekvienas mokymas registruojamas klasterio MLflow: parametrai, metrikos per žingsnius, sistemos metrikos, modelis su aplinka, duomenų rinkinys, `git_commit`, `git_dirty`, `dvc_raw_md5`, `seed` tag'ai | Must |
| FR-04 | Mokymas supakuotas į Docker vaizdą, paleidžiamą be vietinės Python aplinkos | Must |
| FR-05 | Mokymas paleidžiamas kaip Kubernetes Job, log'inantis į klasterio MLflow; parametrai per ConfigMap, MLflow prisijungimai per Secret | Must |
| FR-06 | Hiperparametrų paieška (Optuna, ≥ 5 bandymai) log'inama kaip įdėtiniai MLflow run'ai po vienu tėviniu; bandymai vertinami validacijos imtyje, ne testinėje | Must |
| FR-07 | Kiekvienas mokymas registruoja `imdb-sentiment` versiją MLflow Model Registry; aptarnaujama versija pažymėta alias'u `@champion` | Must |
| FR-08 | Inferencijos API klasteryje: `GET /health` (modelio versija) ir `POST /predict`; modelis įkeliamas iš `models:/imdb-sentiment@champion`, ne iš failo vaizde | Must |
| FR-09 | CI kiekvienam push'ui: ruff, unit testai, serve vaizdo build ir push į GHCR `sha-<commit>` | Must |
| FR-10 | CD: testai → `dvc repro` → kokybės vartas → `@champion` → manifesto atnaujinimas → deploy; nepraėjus vartui deploy nevyksta | Must |
| FR-11 | Rollback į ankstesnę modelio versiją: `promote.py --version <n>` ir `rollout restart` | Must |

## 3. Nefunkciniai reikalavimai

| ID | Kategorija | Reikalavimas | KPI (patikra) | Išmatuota |
| --- | --- | --- | --- | --- |
| NFR-01 | Kokybė | Modelis testinėje imtyje geresnis už atsitiktinį spėjimą | accuracy ≥ 0,85 ir F1 ≥ 0,85 (`metrics.json`) | U1: C = 0,1 / 1 / 10: accuracy 0,8762 / 0,9036 / 0,9078. U2 (C 20,5, bigramos): accuracy 0,9065, F1 0,9075 |
| NFR-02 | Vertinimo validumas | Tas pats atsiliepimas nepatenka į abi imtis | 0 bendrų tekstų tarp `train` ir `test` (README patikra) | 0 (be dublikatų šalinimo būtų galimi 418) |
| NFR-03 | Našumas | Mokymo trukmė CPU | MLflow run'o trukmė ≤ 2 min | 45 s (`dvc repro`, su mokymosi kreive ir registravimu); k8s Job 110 s; CD `dvc repro` žingsnis ~72 s |
| NFR-04 | Atkartojamumas | Istorinis run'as atkuriamas `python reproduce.py <run_id>` | ≤ 2 min; \|Δaccuracy\|, \|ΔF1\| ≤ 0,005 | 23 s, Δ = 0,0000 abiem (`45659219` atkurtas kaip `d8ebe1c0`) |
| NFR-05 | Patikimumas | MLflow duomenys išlieka perkūrus Pod'us | 0 prarastų run'ų ir artefaktų po `kubectl delete pod -l app=mlflow` ir `-l app=postgres` | 4/4 run'ai ir artefaktai išliko; modelis įkeliamas iš MLflow |
| NFR-06 | Saugumas | MLflow su prisijungimu, nepasiekiamas iš tinklo; paslapčių nėra Git | basic auth (be slaptažodžio 401); klausosi tik `127.0.0.1:5050`; 0 slaptažodžių Git istorijoje (`git log -p \| grep`) | basic auth įjungtas; tik `127.0.0.1:5050`; slaptažodžiai tik Secret `mlflow-credentials` ir GitHub repo secret'uose, Git istorijoje 0 |
| NFR-07 | Atsekamumas | Run'as susietas su kodu ir duomenimis | 100 % run'ų turi `git_commit`, `git_dirty=false`, `dvc_raw_md5` = `data/raw.dvc` md5 | 100 % (`caf919ef…`) |
| NFR-08 | Vaizdo sauga | Vaizdai be kritinių spragų, ne root | Trivy CRITICAL = 0 (`--exit-code 1` vartas); UID ≠ 0 | train: CRITICAL 0, HIGH 44; serve: CRITICAL 0, HIGH 51 (Debian bazė, be pataisų); abu UID 1000 |
| NFR-09 | Vaizdo dydis | Mokymo vaizdas tinka laboratorijos kompiuteriui | rootfs ≤ 1 GB (`docs/docker-image.md`) | 818 MB |
| NFR-10 | Našumas | API vėlinimas | p95 ≤ 100 ms, 200 nuoseklių užklausų (`scripts/load_test.py`) | **p95 13,4 ms** (p50 4,1, p99 23,1 ms), per `port-forward` ([`load-test.md`](load-test.md)) |
| NFR-11 | Našumas | API pralaidumas | ≥ 50 užklausų/s, vienas klientas, nuosekliai | **173 užklausų/s**, 0 klaidų iš 200 |
| NFR-12 | Dydis | Modelio artefakto dydis | `model.pkl` ≤ 50 MB (MLflow artefaktai) | **2,3 MB** (v1, `@champion`) |
| NFR-13 | Dydis | Inferencijos vaizdas | rootfs ≤ 1 GB | 780 MB rootfs (`docker images`: 1,05 GB) |
| NFR-14 | Kokybės vartas | Modelis žemiau slenksčio neįdiegiamas | `accuracy ≥ gate.min_accuracy` (0,88, `params.yaml`); raudonas CD paleidimas neatlieka deploy | žalias: 0,9065 ≥ 0,88, deploy v3 ([run](https://github.com/nojusbuc/mlops-u1/actions/runs/43103153565)); raudonas (0,99): FAIL, deploy praleistas ([run](https://github.com/nojusbuc/mlops-u1/actions/runs/43105940052)) |
| NFR-15 | Patikimumas | Rollback trukmė | ankstesnė versija aptarnaujama ≤ 2 min po `promote.py` + `rollout restart` | _[matuojama gynime]_ |

## 4. Keitimo istorija

| Versija | Data | Autorius | Pakeitimai |
| --- | --- | --- | --- |
| 1.0 | 2026-10-21 | nojusbuc | Pradinis dokumentas: problema, duomenys, FR, NFR su KPI |
| 1.1 | 2026-10-21 | nojusbuc | Visos reikšmės išmatuotos klasterio run'uose; nauji NFR-07 (atsekamumas), NFR-08–09 (vaizdas) |
| 1.2 | 2026-11-11 | nojusbuc | Tracking: metrikos per žingsnius (mokymosi kreivė), sistemos metrikos, `seed`; Optuna HPO su įdėtiniais run'ais (FR-06); FR-03 papildytas |
| 1.3 | 2026-11-11 | nojusbuc | Model Registry ir `@champion` (FR-07); MLflow basic auth, prisijungimai per Secret, Job juos skaito (FR-05, NFR-06) |
| 1.4 | 2026-11-11 | nojusbuc | Inferencijos API (FR-08); apkrovos testas (NFR-10, NFR-11); modelio ir vaizdo dydis (NFR-12, NFR-13); NFR-08 papildytas serve vaizdu |
| 1.5 | 2026-11-11 | nojusbuc | CI (FR-09); CD su kokybės vartu ir rollback (FR-10, FR-11, NFR-14, NFR-15) |
| 1.6 | 2026-11-11 | nojusbuc | Naujos NFR išmatuotos; NFR-01, NFR-03 atnaujinti U2 modeliu |

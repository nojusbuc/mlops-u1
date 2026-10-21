# IMDB atsiliepimų nuotaikos klasifikatorius: reikalavimai

**Versija:** 1.1
**Data:** 2026-10-21
**Autorius:** Nojus (nojusbuc)

## 1. Apimtis

**Problema.** Pagal filmo atsiliepimo tekstą nustatyti, ar jis teigiamas, ar neigiamas (dvejetainė klasifikacija).
Vertinamas ne modelio SOTA, o atkartojamas srautas aplink jį: DVC pipeline'as, klasterio MLflow, Docker vaizdas.

**Duomenys.** Hugging Face `stanfordnlp/imdb`, fiksuota revizija `e6281661ce1c48d982bc483cf8a173c1bbeb5d31`
(Large Movie Review Dataset, Maas et al., 2011). Naudojami `train` ir `test` failai: 50 000 atsiliepimų su žymomis,
klasės subalansuotos 50/50. 418 atsiliepimų pasikartoja (prieštaringų žymų nėra), todėl jie pašalinami prieš padalijimą,
kad tas pats tekstas nepatektų ir į mokymo, ir į testinę imtį. Lieka 49 582; stratifikuotas padalijimas 80/20
(`params.yaml` `prepare`): 39 664 mokymui, 9 917 testui, abiejose 50,2 % teigiamų.

**Modelis.** TF-IDF (žodžiai ir bigramos) + logistinė regresija, mokoma CPU per sekundes.
Klasės subalansuotos, todėl pagrindinė metrika yra **accuracy**, papildomai F1. Atsitiktinio spėjimo bazė 0,50.

## 2. Funkciniai reikalavimai

| ID | Reikalavimas | Prioritetas |
|---|---|---|
| FR-01 | Modelis pagal atsiliepimo tekstą grąžina klasę: 1 (teigiamas) arba 0 (neigiamas) | Must |
| FR-02 | `dvc.yaml` pipeline'as `prepare → train → evaluate` iš DVC versijuotų duomenų sukuria modelį ir `metrics.json` | Must |
| FR-03 | Kiekvienas mokymas registruojamas klasterio MLflow: parametrai, metrikos, modelis, duomenų rinkinys, `git_commit`, `git_dirty`, `dvc_raw_md5` tag'ai | Must |
| FR-04 | Mokymas supakuotas į Docker vaizdą, paleidžiamą be vietinės Python aplinkos | Must |
| FR-05 | Mokymas paleidžiamas kaip Kubernetes Job, log'inantis į klasterio MLflow | Should |

## 3. Nefunkciniai reikalavimai

| ID | Kategorija | Reikalavimas | KPI (patikra) | Išmatuota |
|---|---|---|---|---|
| NFR-01 | Kokybė | Modelis testinėje imtyje geresnis už atsitiktinį spėjimą | accuracy ≥ 0,85 ir F1 ≥ 0,85 (`metrics.json`) | C = 0,1 / 1 / 10: accuracy 0,8762 / 0,9036 / 0,9078, F1 0,8797 / 0,9052 / 0,9090; tenkina visi |
| NFR-02 | Vertinimo validumas | Tas pats atsiliepimas nepatenka į abi imtis | 0 bendrų tekstų tarp `train` ir `test` (README patikra) | 0 (be dublikatų šalinimo būtų galimi 418) |
| NFR-03 | Našumas | Mokymo trukmė CPU | MLflow run'o trukmė ≤ 2 min | 15 s (`dvc repro`), 21–22 s Docker / k8s Job |
| NFR-04 | Atkartojamumas | Istorinis run'as atkuriamas `python reproduce.py <run_id>` | ≤ 2 min; \|Δaccuracy\|, \|ΔF1\| ≤ 0,005 | 23 s, Δ = 0,0000 abiem (`45659219` atkurtas kaip `d8ebe1c0`) |
| NFR-05 | Patikimumas | MLflow duomenys išlieka perkūrus Pod'us | 0 prarastų run'ų ir artefaktų po `kubectl delete pod -l app=mlflow` ir `-l app=postgres` | 4/4 run'ai ir artefaktai išliko; modelis įkeliamas iš MLflow |
| NFR-06 | Saugumas | MLflow nepasiekiamas iš tinklo, paslapčių nėra Git | klausosi tik `127.0.0.1:5050` (`lsof`); 0 slaptažodžių Git (`git grep`) | tik `127.0.0.1:5050`; 0 (Git'e tik Secret raktų pavadinimai) |
| NFR-07 | Atsekamumas | Run'as susietas su kodu ir duomenimis | 100 % run'ų turi `git_commit`, `git_dirty=false`, `dvc_raw_md5` = `data/raw.dvc` md5 | 100 % (`caf919ef…`) |
| NFR-08 | Vaizdo sauga | Mokymo vaizdas be kritinių spragų, ne root | Trivy CRITICAL = 0 (`--exit-code 1` vartas); UID ≠ 0 | CRITICAL 0, HIGH 44 (Debian, be pataisų); UID 1000 |
| NFR-09 | Vaizdo dydis | Mokymo vaizdas tinka laboratorijos kompiuteriui | rootfs ≤ 1 GB (`docs/docker-image.md`) | 818 MB |

## 4. Keitimo istorija

| Versija | Data | Autorius | Pakeitimai |
|---|---|---|---|
| 1.0 | 2026-10-21 | nojusbuc | Pradinis dokumentas: problema, duomenys, FR, NFR su KPI |
| 1.1 | 2026-10-21 | nojusbuc | Visos reikšmės išmatuotos klasterio run'uose; nauji NFR-07 (atsekamumas), NFR-08–09 (vaizdas) |

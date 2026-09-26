# Fixtures de contrato

`mobile_snapshot_v1.json` foi capturado diretamente do
`MobileSnapshotBuilder` do projeto Desktop AlertaM, sem Selenium e sem rede.

Fonte usada na revisão de 2026-09-25:

- projeto Desktop: `/home/ciro/dev/prog/alertamaritimo`
- builder: `src/alertam/application/mobile_snapshot.py`
- contrato: `specs/017-snapshot-mobile-sync-desktop.md`
- SHA-256 da fixture: `6a40fc97e36eefc07fac36e8ee02cf2ce589b942f2cbe34521723e65699322a9`

Antes da Task 10, a fixture foi regenerada pelo builder real e comparada byte a byte
com a cópia versionada nesta API; o resultado foi idêntico.

A API não importa módulos do Desktop em runtime. Esta fixture é a fronteira estática
versionada entre os dois projetos.

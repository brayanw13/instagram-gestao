# Posts de gestão empresarial — publicação automática

Imagens e agenda dos posts de @brayancruz_gestaoempresarial, publicados diariamente pelo GitHub Actions.

- `agenda.json`: o que sai em cada dia
- `publicados.json`: o que já foi publicado
- `posts/`: imagens (JPEG 1080x1350)
- `publicar.py`: publicador (Graph API do Instagram)
- `scripts/montar_agenda.py`: adiciona um novo ciclo de 30 dias
- `CONFIGURAR.md`: configuração inicial e rotina

## LinkedIn

Posts do perfil pessoal no LinkedIn, publicados diariamente por outro workflow (`publicar-linkedin.yml`).

- `agenda-linkedin.json`: o que sai em cada dia (formatos: documento em PDF, imagem ou texto)
- `publicados-linkedin.json`: o que já foi publicado
- `posts-linkedin/`: PDFs e imagens
- `publicar_linkedin.py`: publicador (API do LinkedIn)
- `scripts/montar_agenda_linkedin.py`: adiciona um ciclo renderizado pelo `render_linkedin.py`
- `CONFIGURAR-LINKEDIN.md`: configuração inicial, renovação do token e rotina

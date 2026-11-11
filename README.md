# central-comando-operacional
Aplicação Streamlit para passagem de turno da Central de Comando

## Banco de dados

A aplicação usa PostgreSQL. No Supabase, crie um projeto e copie a URL de
conexão do pooler (Transaction ou Session), com SSL habilitado. Configure a
mesma variável `DATABASE_URL` localmente em `.streamlit/secrets.toml`:

```toml
DATABASE_URL = "postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@<POOLER_HOST>:6543/postgres?sslmode=require"
```

No Streamlit Community Cloud, adicione esse conteúdo em **App settings >
Secrets**. Não envie `secrets.toml` ao Git. A aplicação cria as tabelas ao
iniciar.

Para levar ao Supabase os dados do arquivo local `central_comando.db`, instale
as dependências e execute a migração na raiz do projeto, com `DATABASE_URL`
configurada localmente:

```powershell
py -m pip install -r requirements.txt
py migrate_database.py
```

O comando mantém o arquivo SQLite original e pode ser executado novamente sem
duplicar a importação. Faça a migração antes de publicar; o arquivo SQLite é
ignorado pelo Git e não é enviado automaticamente ao Streamlit Cloud.

No módulo Conectividade, os dados da loja são localizados pelos cabeçalhos da
primeira linha da planilha base. Incidentes de lojas isoladas podem registrar
dois links em uma única ação, com situação, protocolo e status independentes
para cada um. A solicitação de envio de 4G e suas informações também são
registradas no incidente somente quando a loja está isolada por link.
Administradores podem carregar ou atualizar a
planilha no módulo Gestão de Usuários. Instale as dependências com
`pip install -r requirements.txt`.

O módulo Lojas em GNET também usa a base para preencher nome e estado da
unidade. O status pode ser definido como aguardando solução, em avaliação
pela equipe de redes ou resolvido.

# central-comando-operacional
Aplicação Streamlit para passagem de turno da Central de Comando

## Banco de dados

A aplicação usa PostgreSQL. No Supabase, abra **Connect**, selecione um pooler
(Session ou Transaction) e copie a URI PostgreSQL completa, incluindo o host e
a porta informados pelo Supabase. Não troque a porta manualmente: Session e
Transaction podem usar portas diferentes. Configure a URI localmente em
`.streamlit/secrets.toml`:

```toml
DATABASE_URL = "postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@<POOLER_HOST>:<PORT>/postgres?sslmode=require"
```

No Streamlit Community Cloud, adicione esse conteúdo em **App settings >
Secrets**. Não envie `secrets.toml` ao Git. A aplicação cria as tabelas ao
iniciar.

Se a conexão falhar no Streamlit Cloud, confira em **Manage app > Logs** a
mensagem original do Psycopg. Erros de resolução de nome indicam host incorreto;
falha de autenticação indica senha/usuário incorretos. Se a senha tiver
caracteres especiais, use a URI copiada pelo Supabase ou faça o URL-encode da
senha. Para projetos com conexão direta IPv6, use o pooler, que é adequado ao
ambiente do Streamlit Cloud.

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

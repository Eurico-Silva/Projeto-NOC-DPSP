# central-comando-operacional
Aplicação Streamlit para passagem de turno da Central de Comando

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

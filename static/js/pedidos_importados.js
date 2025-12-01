async function abrirDetalhes(nnota) {
    const modal = new bootstrap.Modal(document.getElementById('modalDetalhesPedido'));

    document.getElementById("conteudo-detalhes").innerHTML = "Carregando...";

    const resp = await fetch(`/detalhar_pedido/${nnota}`);
    const dados = await resp.json();

    if (!dados || !dados.pedido) {
        document.getElementById("conteudo-detalhes").innerHTML = "Erro ao carregar o pedido.";
        modal.show();
        return;
    }

    let html = `
        <h5>Pedido nº ${dados.pedido.n_nota}</h5>
        <p><b>Cliente:</b> ${dados.pedido.nome_cliente}</p>
        <p><b>Endereço:</b> ${dados.pedido.endereco || ''} ${dados.pedido.numero || ''}, 
                           ${dados.pedido.bairro || ''}, ${dados.pedido.cidade || ''}</p>

        <h6 class="mt-4">Produtos</h6>
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>Produto</th>
                    <th>Classificação</th>
                    <th>Quantidade</th>
                </tr>
            </thead>
            <tbody>
    `;

    for (const item of dados.itens) {
        html += `
            <tr>
                <td>${item.nome_produto}</td>
                <td>
                    ${item.classificacao_texto === "Agrotóxico" 
                        ? "<span class='badge bg-danger'>Agrotóxico</span>"
                        : "<span class='badge bg-success'>Normal</span>"
                    }
                </td>
                <td>${item.quant_pedido}</td>
            </tr>
        `;
    }

    html += `
            </tbody>
        </table>
    `;

    document.getElementById("conteudo-detalhes").innerHTML = html;
    modal.show();
}

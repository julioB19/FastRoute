// =======================================================
// FUNÇÃO PARA ABRIR DETALHES DO PEDIDO
// =======================================================
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



// =======================================================
// PREPARAÇÃO DOS FILTROS (multi seleção e persistência)
// =======================================================

// Converte string "Maria,João" em ["Maria","João"]
function separarValoresMultiplo(valor) {
    if (!valor) return [];
    return valor
        .split(",")
        .map(v => v.trim())
        .filter(v => v.length > 0);
}



// =======================================================
// APLICA FILTROS DO FORMULÁRIO
// =======================================================
function aplicarFiltros() {

    const params = new URLSearchParams();

    // -----------------------------
    // FILTROS PRINCIPAIS
    // -----------------------------
    const filtroStatus = document.getElementById("filtro-status").value;
    if (filtroStatus) params.set("filtro", filtroStatus);

    const dataNota = document.getElementById("data_nota").value;
    if (dataNota) params.set("data_nota", dataNota);

    const itensPP = document.getElementById("itens_por_pagina").value;
    if (itensPP) params.set("itens", itensPP);



    // -----------------------------
    // MULTI-SELEÇÃO DE CLIENTES
    // -----------------------------
    const campoCliente = document.getElementById("cliente_nome").value.trim();
    const multiClientes = document.getElementById("clientes_multi");

    // valores separados por vírgula
    const listaSimples = separarValoresMultiplo(campoCliente);
    const listaMulti = Array.from(multiClientes.selectedOptions).map(o => o.value);

    const finalClientes = [...listaSimples, ...listaMulti];

    if (finalClientes.length > 0) {
        params.set("cliente_nome", finalClientes.join(","));
    }



    // -----------------------------
    // MULTI-SELEÇÃO NOTAS
    // -----------------------------
    const campoNota = document.getElementById("numero_nota").value.trim();
    const multiNotas = document.getElementById("notas_multi");
    const notasSimples = separarValoresMultiplo(campoNota);
    const notasMulti = Array.from(multiNotas.selectedOptions).map(o => o.value);

    const finalNotas = [...notasSimples, ...notasMulti];
    if (finalNotas.length > 0) {
        params.set("numero_nota", finalNotas.join(","));
    }



    // -----------------------------
    // CAMPOS LIVRES
    // -----------------------------
    const endereco = document.getElementById("endereco").value.trim();
    if (endereco) params.set("endereco", endereco);

    const cidade = document.getElementById("cidade").value.trim();
    if (cidade) params.set("cidade", cidade);

    const entrega = document.getElementById("data_entrega").value.trim();
    if (entrega) params.set("data_entrega", entrega);



    // -----------------------------
    // REDIRECIONA COM FILTROS
    // -----------------------------
    window.location = "/pedidos_importados?" + params.toString();
}



// =======================================================
// LIMPAR FILTROS
// =======================================================
function limparFiltros() {
    window.location = "/pedidos_importados";
}


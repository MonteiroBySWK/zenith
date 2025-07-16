// Dashboard atualizado com dados reais da API

const input = document.querySelector('input[type="file"]');
const btn = document.querySelector("button");
const result = document.querySelector("#result");
const ctxLine = document.getElementById('lineChart')?.getContext('2d');
const ctxBar = document.getElementById('barChart')?.getContext('2d');
const calendarGrid = document.getElementById("calendarGrid");

// Adiciona integração com KPI baseado na API /api/lotes/{produto_sku}
async function atualizarKPIs(sku) {
  try {
    const res = await fetch(`http://localhost:5000/api/lotes/${sku}`);
    const data = await res.json();
    const metricas = data.metricas;

    const totalInicial = metricas.total_inicial;
    const totalAtual = metricas.total_atual;
    const totalDisponivel = metricas.total_disponivel;

    const totalRetiradoHoje = (totalInicial - totalAtual).toFixed(1);
    const emDescongelamento = (totalInicial - totalDisponivel).toFixed(1);

    document.getElementById("kpi-retirado").textContent = `${totalRetiradoHoje} kg`;
    document.getElementById("kpi-descongelando").textContent = `${emDescongelamento} kg`;
    document.getElementById("kpi-disponivel").textContent = `${totalDisponivel.toFixed(1)} kg`;
  } catch (error) {
    console.error("Erro ao carregar KPIs:", error);
  }
}

// Novo: gráfico de linha e barras com base na API /api/dashboard
async function carregarDashboard() {
  try {
    const res = await fetch("http://localhost:5000/api/dashboard");
    const data = await res.json();

    if (ctxLine) {
      const vendas = data.detalhes.evolucao_vendas;
      const previsao = data.detalhes.previsoes_demanda;

      const labels = vendas.map(v => v.dia);
      const dadosReais = vendas.map(v => v.total);
      const dadosPrevistos = previsao.map(p => p.quantidade);

      new Chart(ctxLine, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Vendas Reais",
              data: dadosReais,
              borderColor: "#1f2937",
              tension: 0.3
            },
            {
              label: "Previsão de Demanda",
              data: dadosPrevistos,
              borderColor: "#e30613",
              borderDash: [5, 5],
              tension: 0.3
            }
          ]
        },
        options: {
          scales: {
            y: { beginAtZero: false }
          }
        }
      });
    }

    if (ctxBar) {
      const topProdutos = data.detalhes.top_produtos;
      const labels = topProdutos.map(p => p.nome);
      const valores = topProdutos.map(p => p.total_vendido);

      new Chart(ctxBar, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [{
            label: 'Volume Vendido (kg)',
            data: valores,
            backgroundColor: '#e30613'
          }]
        },
        options: {
          plugins: {
            legend: { display: false }
          },
          scales: {
            y: {
              beginAtZero: true,
              title: { display: true, text: 'Kg Vendidos' }
            },
            x: {
              title: { display: true, text: 'SKU / Produto' }
            }
          }
        }
      });
    }
  } catch (error) {
    console.error("Erro ao carregar dados do dashboard:", error);
  }
}

// Chamada inicial das funções principais
atualizarKPIs("237478");
carregarDashboard();

document.getElementById('dataAtual').textContent = new Date().toLocaleDateString('pt-BR');

// Upload CSV
btn.addEventListener("click", async (e) => {
  e.preventDefault();

  if (!input.files.length) {
    result.innerHTML = "<p class='text-red-600'>Selecione um arquivo primeiro.</p>";
    return;
  }

  const formData = new FormData();
  formData.append("file", input.files[0]);

  try {
    const res = await fetch("http://localhost:8080/predict", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) throw new Error("Erro na requisição: " + res.status);

    const data = await res.json();

    if (data?.colunas && data?.colunas_nome) {
      result.innerHTML = `
        <p><strong>Colunas:</strong> ${data.colunas}</p>
        <p><strong>Linhas:</strong> ${data.linhas}</p>
        <p><strong>Nomes das colunas:</strong> ${data.colunas_nome.join(", ")}</p>
      `;
    } else {
      result.innerHTML = "<p class='text-red-600'>Resposta inesperada do servidor.</p>";
    }
  } catch (err) {
    console.error(err);
    result.innerHTML = `<p class='text-red-600'>Erro: ${err.message}</p>`;
  }
});

// Calendário com filtro
function gerarCalendario(mes = new Date().getMonth(), ano = new Date().getFullYear()) {
  if (!calendarGrid) return;

  calendarGrid.innerHTML = "";

  const diasSemana = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
  diasSemana.forEach(dia => {
    const header = document.createElement("div");
    header.className = "font-bold text-gray-500";
    header.textContent = dia;
    calendarGrid.appendChild(header);
  });

  const primeiroDia = new Date(ano, mes, 1);
  const ultimoDia = new Date(ano, mes + 1, 0);
  const inicioSemana = primeiroDia.getDay();
  const totalDias = ultimoDia.getDate();

  for (let i = 0; i < inicioSemana; i++) {
    const vazio = document.createElement("div");
    calendarGrid.appendChild(vazio);
  }

  for (let dia = 1; dia <= totalDias; dia++) {
    const div = document.createElement("div");
    const valor = Math.floor(Math.random() * 3);
    const peso = Math.floor(Math.random() * 200) + 50;

    const statusClass = valor === 2 ? "high" :
                        valor === 1 ? "medium" : "low";

    div.className = statusClass;
    div.setAttribute("data-tooltip", `Dia ${dia}: ${peso} kg`);
    div.setAttribute("data-status", statusClass);
    div.textContent = dia.toString().padStart(2, '0');

    calendarGrid.appendChild(div);
  }
}

// Inicializar calendário e filtro
gerarCalendario();

document.getElementById('filtroCritico')?.addEventListener('change', (e) => {
  const valor = e.target.value;
  document.querySelectorAll("#calendarGrid div").forEach(div => {
    if (!div.hasAttribute("data-status")) return;
    div.style.display = (valor === "all" || div.getAttribute("data-status") === valor) ? "block" : "none";
  });
});

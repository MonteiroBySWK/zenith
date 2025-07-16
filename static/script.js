const ctxLine = document.getElementById('lineChart')?.getContext('2d');
const ctxBar = document.getElementById('barChart')?.getContext('2d');
const calendarGrid = document.getElementById("calendarGrid");

async function atualizarKPIs_e_Graficos(sku) {
  try {
    const res = await fetch(`http://localhost:5000/api/lotes/${sku}`);
    if (!res.ok) throw new Error("Falha na API /api/lotes");

    const data = await res.json();
    const metricas = data.metricas;

    // === KPIs ===
    const totalInicial = Number(metricas.total_inicial) || 0;
    const totalAtual = Number(metricas.total_atual) || 0;
    const totalDisponivel = Number(metricas.total_disponivel) || 0;

    const totalRetiradoHoje = (totalInicial - totalAtual).toFixed(1);
    const emDescongelamento = (totalInicial - totalDisponivel).toFixed(1);

    document.getElementById("kpi-retirado").textContent = `${totalRetiradoHoje} kg`;
    document.getElementById("kpi-descongelando").textContent = `${emDescongelamento} kg`;
    document.getElementById("kpi-disponivel").textContent = `${totalDisponivel.toFixed(1)} kg`;

    // Se tiver o ID kpi-status, atualiza
    if (document.getElementById("kpi-status") && metricas.lotes_por_status?.descongelando !== undefined) {
      document.getElementById("kpi-status").textContent = `Descongelando: ${metricas.lotes_por_status.descongelando}`;
    }

    // === Gráfico de Vendas com Previsão ===
    const vendas = data.evolucao_vendas || [];
    const previsao = data.previsoes_demanda || [];

    if (ctxLine && vendas.length && previsao.length) {
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
          responsive: true,
          plugins: {
            title: {
              display: true,
              text: "Histórico de Vendas com Previsão"
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Quantidade (kg)'
              }
            },
            x: {
              title: {
                display: true,
                text: 'Data'
              }
            }
          }
        }
      });
    }

    // === Distribuição de Vendas por SKU ===
    if (ctxBar && data.top_produtos) {
      const labels = data.top_produtos.map(p => p.nome);
      const valores = data.top_produtos.map(p => p.total_vendido);

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
    console.error("Erro ao carregar dados:", error);
    document.getElementById("kpi-retirado").textContent = "-";
    document.getElementById("kpi-descongelando").textContent = "-";
    document.getElementById("kpi-disponivel").textContent = "-";
    if (document.getElementById("kpi-status")) {
      document.getElementById("kpi-status").textContent = "Erro";
    }
  }
}

// Função para gerar calendário fictício
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

    const statusClass = valor === 2 ? "high" : valor === 1 ? "medium" : "low";
    div.className = statusClass;
    div.setAttribute("data-tooltip", `Dia ${dia}: ${peso} kg`);
    div.setAttribute("data-status", statusClass);
    div.textContent = dia.toString().padStart(2, '0');
    calendarGrid.appendChild(div);
  }
}

// Filtro do calendário
document.getElementById('filtroCritico')?.addEventListener('change', (e) => {
  const valor = e.target.value;
  document.querySelectorAll("#calendarGrid div").forEach(div => {
    if (!div.hasAttribute("data-status")) return;
    div.style.display = (valor === "all" || div.getAttribute("data-status") === valor) ? "block" : "none";
  });
});

// Inicialização após DOM carregar
document.addEventListener("DOMContentLoaded", () => {
  atualizarKPIs_e_Graficos("237478");
  gerarCalendario();
});

const input = document.querySelector('input[type="file"]');
const btn = document.querySelector("button");
const result = document.querySelector("#result");
const ctxLine = document.getElementById('lineChart')?.getContext('2d');
const ctxBar = document.getElementById('barChart')?.getContext('2d');
const calendarGrid = document.getElementById("calendarGrid");

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

// Gráfico de linha
if (ctxLine) {
  const vendasReais = Array.from({ length: 60 }, () => Math.floor(Math.random() * 60) + 90);
  const datas = Array.from({ length: 60 }, (_, i) => `2025-06-${String(i + 1).padStart(2, '0')}`);
  const previsao = vendasReais.map((v, i) => i > 3 ? Math.round((v + vendasReais[i - 1] + vendasReais[i - 2]) / 3) : v);

  new Chart(ctxLine, {
    type: 'line',
    data: {
      labels: datas,
      datasets: [
        {
          label: 'Vendas Reais',
          data: vendasReais,
          borderColor: '#1f2937',
          tension: 0.4,
        },
        {
          label: 'Previsão (Média Móvel)',
          data: previsao,
          borderColor: '#e30613',
          borderDash: [5, 5],
          tension: 0.3,
        },
      ]
    },
    options: {
      plugins: {
        title: { display: false }
      },
      scales: {
        y: { beginAtZero: false }
      }
    }
  });
}

// Gráfico de barras por SKU
if (ctxBar) {
  const skuLabels = ['SKU 101', 'SKU 102', 'SKU 103', 'SKU 104', 'SKU 105', 'SKU 106', 'SKU 107', 'SKU 108', 'SKU 109', 'SKU 110'];
  const skuData = skuLabels.map(() => Math.floor(Math.random() * 250) + 100);

  new Chart(ctxBar, {
    type: 'bar',
    data: {
      labels: skuLabels,
      datasets: [{
        label: 'Volume Vendido (kg)',
        data: skuData,
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
          title: {
            display: true,
            text: 'Kg Vendidos'
          }
        },
        x: {
          title: {
            display: true,
            text: 'SKU'
          }
        }
      }
    }
  });
}

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
gerarCalendario();

document.getElementById('filtroCritico')?.addEventListener('change', (e) => {
  const valor = e.target.value;
  document.querySelectorAll("#calendarGrid div").forEach(div => {
    if (!div.hasAttribute("data-status")) return;
    div.style.display = (valor === "all" || div.getAttribute("data-status") === valor) ? "block" : "none";
  });
});

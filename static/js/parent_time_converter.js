document.addEventListener("DOMContentLoaded", function() {
    // Encontra todos os spans de tempo que precisam de conversão
    const timeSpans = document.querySelectorAll(".submission-time");
    
    // Pega a data de "hoje" e "ontem" no fuso horário local
    const hoje = new Date();
    const ontem = new Date();
    ontem.setDate(ontem.getDate() - 1);

    timeSpans.forEach(span => {
        // Pega a data UTC enviada pelo servidor
        const utcIsoString = span.dataset.utcTime;
        if (!utcIsoString) return;

        try {
            // Converte a string UTC para um objeto Date (já no fuso local)
            const dataLocal = new Date(utcIsoString);

            // Formata a hora (ex: 14:30)
            const hora = dataLocal.getHours().toString().padStart(2, '0');
            const minuto = dataLocal.getMinutes().toString().padStart(2, '0');
            const horaFormatada = `${hora}:${minuto}`;

            let diaFormatado = "";

            // Compara as datas (ignorando a hora)
            if (dataLocal.toDateString() === hoje.toDateString()) {
                diaFormatado = "Enviado hoje às";
            } else if (dataLocal.toDateString() === ontem.toDateString()) {
                diaFormatado = "Enviado ontem às";
            } else {
                // Formato padrão (ex: 08/11)
                const dia = dataLocal.getDate().toString().padStart(2, '0');
                const mes = (dataLocal.getMonth() + 1).toString().padStart(2, '0');
                diaFormatado = `Enviado em ${dia}/${mes} às`;
            }

            // Atualiza o texto no HTML
            span.textContent = `${diaFormatado} ${horaFormatada}`;

        } catch (e) {
            console.error("Erro ao formatar data:", e);
            span.textContent = "Enviado (data inválida)";
        }
    });
});
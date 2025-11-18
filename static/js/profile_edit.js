// Espera o documento HTML carregar
document.addEventListener("DOMContentLoaded", () => {

    // 1. Encontra os dois elementos de que precisamos
    const fileInput = document.getElementById("foto_perfil");
    const imagePreview = document.getElementById("image-preview");

    // (Verificação de segurança: só roda se os elementos existirem)
    if (fileInput && imagePreview) {
        // 2. "Ouve" por mudanças no <input type="file">
        fileInput.addEventListener("change", function() {

            // 3. Pega no ficheiro que o utilizador escolheu
            const file = this.files[0];

            if (file) {
                // 4. Se um ficheiro foi escolhido, cria um "leitor" de ficheiros
                const reader = new FileReader();

                // 5. Diz ao leitor o que fazer quando ele terminar de ler
                reader.onload = function(event) {
                    // 6. Atualiza o 'src' (a fonte) da imagem com o
                    //    resultado da leitura do ficheiro.
                    imagePreview.src = event.target.result;
                }

                // 7. Manda o leitor ler o ficheiro (isto ativa o passo 5)
                reader.readAsDataURL(file);
            }
        });
    }
});
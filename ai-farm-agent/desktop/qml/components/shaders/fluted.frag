// Vidro canelado sobre o fundo: nervuras verticais que refratam (deslocam) a imagem na horizontal,
// com faixas de luz e sombra estreitas. Distorcao muito maior em x; resposta minima ao ponteiro.
#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float ribs;      // nervuras na largura
    float amount;    // 0..1
    float pointer;   // 0..1 (x do cursor)
};
layout(binding = 1) uniform sampler2D source;

void main() {
    vec2 uv = qt_TexCoord0;
    float wave = 0.012 * sin(uv.y * 5.0 + time * 0.35) + 0.01 * (pointer - 0.5);
    float rib = fract((uv.x + wave) * ribs);
    float bend = (rib - 0.5);                       // -0.5..0.5 dentro de cada nervura
    vec2 suv = vec2(uv.x + bend * 0.045 * amount, uv.y + bend * 0.004 * amount);
    vec4 col = texture(source, clamp(suv, 0.0, 1.0));
    float light = smoothstep(0.0, 0.35, rib) * (1.0 - smoothstep(0.75, 1.0, rib));
    col.rgb *= mix(1.0, 0.90 + 0.16 * light, amount);
    fragColor = col * qt_Opacity;
}

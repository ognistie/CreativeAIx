// Malha de gradiente organica (wallpaper ambiente): 4 cores da paleta em regioes que derivam devagar
// e se fundem (dominio deformado), com grao muito fino para nao formar degraus. Sem textura de entrada.
#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;      // segundos (o QML so avanca quando o fundo deve se mover)
    float aspect;    // largura / altura
    float grain;     // 0..1
    float strength;  // 0..1: intensidade das cores sobre a base
    vec4 c0;         // base
    vec4 c1;
    vec4 c2;
    vec4 c3;
};

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void main() {
    vec2 uv = qt_TexCoord0;
    vec2 p = vec2(uv.x * aspect, uv.y);
    float t = time * 0.06;
    // dominio deformado: as regioes ondulam como seda, sem bordas nitidas
    p += 0.18 * vec2(sin(p.y * 2.3 + t * 1.7), cos(p.x * 1.9 - t * 1.3));
    p += 0.08 * vec2(sin(p.y * 4.1 - t * 2.1), cos(p.x * 3.7 + t * 1.1));

    // tres regioes de cor que derivam (cantos e base) sobre a cor de fundo; cada uma se funde por cima
    vec2 a = vec2(aspect * (0.12 + 0.10 * sin(t * 1.1)), 0.10 + 0.12 * cos(t * 0.9));
    vec2 b = vec2(aspect * (0.88 + 0.08 * cos(t * 0.8)), 0.18 + 0.14 * sin(t * 1.3));
    vec2 c = vec2(aspect * (0.45 + 0.18 * sin(t * 0.7 + 1.0)), 0.95 + 0.08 * cos(t * 1.2));

    float wa = exp(-2.4 * dot(p - a, p - a));
    float wb = exp(-2.6 * dot(p - b, p - b));
    float wc = exp(-2.0 * dot(p - c, p - c));
    vec3 col = c0.rgb;
    col = mix(col, c1.rgb, wa * strength);
    col = mix(col, c2.rgb, wb * strength);
    col = mix(col, c3.rgb, wc * strength);

    col += (hash(uv * 913.0 + fract(time)) - 0.5) * 0.018 * grain;
    fragColor = vec4(col, 1.0) * qt_Opacity;
}

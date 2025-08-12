from PIL import Image

def apply_rgb_filter(input_path, output_path, r_factor=1.0, g_factor=1.0, b_factor=1.0, r_offset=0, g_offset=0, b_offset=0):
    img = Image.open(input_path).convert('RGB')
    pixels = img.load()

    width, height = img.size

    for x in range(width):
        for y in range(height):
            r, g, b = pixels[x, y]

            new_r = int(r * r_factor + r_offset)
            new_g = int(g * g_factor + g_offset)
            new_b = int(b * b_factor + b_offset)

            new_r = max(0, min(255, new_r))
            new_g = max(0, min(255, new_g))
            new_b = max(0, min(255, new_b))

            pixels[x, y] = (new_r, new_g, new_b)

    img.save(output_path)

if __name__ == "__main__":
    input_image = "input.png"
    output_image = "output.png"

    apply_rgb_filter(
        input_image,
        output_image,
        r_factor=34/255,
        g_factor=36/255,
        b_factor=54/255,
        r_offset=0,
        g_offset=0,
        b_offset=0
    )
# write comment about the code above
# this python program applies a simple RGB filter to an input image. The filter uses three parameters: r_factor, g_factor, and b_factor which determine the strength of the red, green, and blue channels respectively. The r_offset, g_offset, and b_offset are used to offset

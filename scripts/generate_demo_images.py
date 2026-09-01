"""Generate fictional package-label PNG fixtures for Step 2."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parents[1] / "samples" / "package_images"

def make_image(filename: str, title: str, lines: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200, 760), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((25, 25, 1175, 735), outline="#19324d", width=8)
    draw.text((70, 70), "SYNTHETIC DEMO PACKAGE", fill="#b42318")
    draw.text((70, 150), title, fill="#19324d")
    for index, line in enumerate(lines):
        draw.text((90, 270 + index * 70), line, fill="black")
    image.save(OUT / filename)

def main() -> None:
    make_image("demo_p001_complete.png", "Sunvale Premium Rice", ["Net Quantity: 500 g", "MRP: ₹120", "Manufactured by: Sunvale Foods Pvt Ltd", "Customer Care: 1800-000-0000"])
    make_image("demo_p002_missing_mrp.png", "BlueKite Instant Oats", ["Net Quantity: 400 g", "Manufactured by: BlueKite Kitchens LLP", "Customer Care: care@bluekite.demo"])
    make_image("demo_p003_missing_contact.png", "MellowMint Herbal Soap", ["Net Quantity: 100 g", "MRP: ₹75", "Manufactured by: MellowMint Careworks"])
    make_image("demo_p004_missing_manufacturer.png", "Northstar Dishwash Gel", ["Net Quantity: 500 ml", "MRP: ₹95", "Customer Care: 1800-000-0000"])
    make_image("demo_p005_suspicious_quantity.png", "CedarGlow Ground Coffee", ["Net Quantity: 5?0 g", "MRP: Rs 240", "Manufactured by: CedarGlow Roasters", "Customer Care: 1800-000-0000"])
    make_image("demo_p006_front.png", "HarborLeaf Green Tea", ["Premium Green Tea", "Net quantity declaration on side panel"])
    make_image("demo_p006_back.png", "HarborLeaf Green Tea", ["Manufactured by: HarborLeaf Trading Co.", "Customer Care: 1800-000-0000"])
    make_image("demo_p006_side.png", "HarborLeaf Green Tea", ["Net Quantity: 250 g", "MRP: ₹180"])

if __name__ == "__main__":
    main()


from pydantic_extra_types.color import Color

colors = {
    "bad": Color("#FF0000"),  # Rojo
    "warning": Color("#FFFF00"),  # Amarillo
    "similar": Color("#0000FF"),  # Azul
    "good": Color("#008000"),  # Verde
    "resalt": Color("#008000"),  # Verde (el mismo que "good")
}

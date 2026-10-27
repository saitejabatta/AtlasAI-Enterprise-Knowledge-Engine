from metadata import extract_metadata
from metadata_overrides import get_table_override


def get_schema_text():

    metadata = extract_metadata()

    schema_text = ""

    for table, columns in metadata.items():
        table_override = get_table_override(
            table
        )

        schema_text += f"\n{table}\n"

        if table_override.get("description"):
            schema_text += (
                f"Description: "
                f"{table_override['description']}\n"
            )

        for col in columns:
            column_name = col[0]
            column_description = table_override.get(
                "columns",
                {}
            ).get(
                column_name,
                ""
            )
            sensitivity = (
                " [sensitive]"
                if column_name in table_override.get(
                    "sensitive_columns",
                    []
                )
                else ""
            )

            if column_description:
                schema_text += (
                    f"- {column_name}: "
                    f"{column_description}"
                    f"{sensitivity}\n"
                )
                continue

            schema_text += (
                f"- {column_name}"
                f"{sensitivity}\n"
            )

    return schema_text

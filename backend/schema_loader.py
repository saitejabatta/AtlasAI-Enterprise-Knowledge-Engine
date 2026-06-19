from metadata import extract_metadata


def get_schema_text():

    metadata = extract_metadata()

    schema_text = ""

    for table, columns in metadata.items():

        schema_text += f"\n{table}\n"

        for col in columns:

            schema_text += f"- {col[0]}\n"

    return schema_text
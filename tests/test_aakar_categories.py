import unittest

from core import aakar_categories as ac

# The 14 labels the UVH-26 checkpoint reports, spelled as it spells them.
MODEL_LABELS = {
    "Hatchback": "Cars/Vans/Jeeps",
    "Sedan": "Cars/Vans/Jeeps",
    "SUV": "Cars/Vans/Jeeps",
    "Van": "Cars/Vans/Jeeps",
    "MUV": "6/8 seater",
    "Three-wheeler": "Auto Rickshaw",
    "Two-wheeler": "Two Wheeler",
    "bicycle": "Cycle",
    "Mini-bus": "Mini Bus",
    "tempo-traveller": "Mini Bus",
    "Bus": "Private Bus",
    "LCV": "LCV",
    "Truck": "2 Axle Truck",
    "Others": "Other",
}

UNSPLIT = ["Taxi", "Govt. Bus", "Goods Auto", "Mini LCV", "3 Axle Truck", "MAV"]

# Road "left" of the real run outputs/62f33e0ec8c4.
LEFT = {"Two-wheeler": 85, "SUV": 31, "Sedan": 29, "Hatchback": 28, "Truck": 26,
        "Three-wheeler": 16, "MUV": 8, "LCV": 8, "Bus": 3}


class CategoriesTest(unittest.TestCase):
    def test_sixteen_categories_in_aakar_order(self):
        self.assertEqual(ac.CATEGORIES, [
            "Cars/Vans/Jeeps", "Taxi", "Auto Rickshaw", "6/8 seater", "Two Wheeler",
            "Cycle", "Mini Bus", "Private Bus", "Govt. Bus", "Goods Auto", "Mini LCV",
            "LCV", "2 Axle Truck", "3 Axle Truck", "MAV", "Other",
        ])

    def test_every_model_label_maps(self):
        for label, category in MODEL_LABELS.items():
            self.assertEqual(ac.to_category(label), category, label)

    def test_spelling_variants_map(self):
        self.assertEqual(ac.to_category("two_wheeler"), "Two Wheeler")
        self.assertEqual(ac.to_category("TEMPO TRAVELLER"), "Mini Bus")

    def test_unknown_label_is_other(self):
        self.assertEqual(ac.to_category("hovercraft"), "Other")

    def test_counts_cover_all_rows_with_dashes_as_none(self):
        counts = ac.count_by_category(LEFT)
        self.assertEqual(list(counts), ac.CATEGORIES)
        for category in UNSPLIT:
            self.assertIsNone(counts[category], category)
        self.assertEqual(counts["Cars/Vans/Jeeps"], 88)
        self.assertEqual(counts["6/8 seater"], 8)
        self.assertEqual(counts["Two Wheeler"], 85)
        self.assertEqual(counts["Auto Rickshaw"], 16)
        self.assertEqual(counts["Private Bus"], 3)
        self.assertEqual(counts["LCV"], 8)
        self.assertEqual(counts["2 Axle Truck"], 26)
        self.assertEqual(counts["Cycle"], 0)
        self.assertEqual(counts["Mini Bus"], 0)
        self.assertEqual(counts["Other"], 0)

    def test_counts_add_up_to_the_road_total(self):
        counts = ac.count_by_category(LEFT)
        self.assertEqual(sum(v for v in counts.values() if v is not None), 234)

    def test_unknown_labels_are_counted_not_dropped(self):
        counts = ac.count_by_category({"hovercraft": 2, "Others": 1})
        self.assertEqual(counts["Other"], 3)

    def test_heading_names_the_model_classes(self):
        self.assertEqual(ac.heading("Cars/Vans/Jeeps"),
                         "Cars/Vans/Jeeps (Hatchback, Sedan, SUV, Van)")
        self.assertEqual(ac.heading("6/8 seater"), "6/8 seater (MUV)")
        self.assertEqual(ac.heading("Mini Bus"), "Mini Bus (Mini-bus, tempo-traveller)")
        self.assertEqual(ac.heading("Private Bus"), "Private Bus (Bus)")
        self.assertEqual(ac.heading("Other"), "Other (Others)")
        self.assertEqual(ac.heading("Taxi"), "Taxi")

    def test_notes_only_for_rows_that_have_a_count(self):
        counts = ac.count_by_category({"Truck": 5, "Three-wheeler": 2})
        self.assertEqual(ac.notes_for(counts), [
            "Auto Rickshaw includes Goods Auto",
            "2 Axle Truck includes 3 Axle Truck and MAV",
        ])
        self.assertEqual(ac.notes_for(ac.count_by_category({"bicycle": 4})), [])

    def test_legend_lists_every_dash(self):
        self.assertEqual(ac.legend(), [
            "Taxi: counted in Cars/Vans/Jeeps",
            "Govt. Bus: counted in Private Bus",
            "Goods Auto: counted in Auto Rickshaw",
            "Mini LCV: counted in LCV",
            "3 Axle Truck: counted in 2 Axle Truck",
            "MAV: counted in 2 Axle Truck",
        ])


if __name__ == "__main__":
    unittest.main()

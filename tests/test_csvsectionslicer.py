from itertools import groupby
from pathlib import Path
from bankroll.csvsectionslicer import parseSectionsForCSV, CSVSectionCriterion, CSVSectionResult

import unittest
from tests import helpers


class TestFidelityPositionSections(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path('tests/fidelity_positions.csv')

    def test_stocksSection(self) -> None:
        with open(self.path, newline='') as csvfile:
            criterion = CSVSectionCriterion(startSectionRowMatch=["Stocks"],
                                            endSectionRowMatch=[""],
                                            rowFilter=lambda r: r[0:7])
            sections = parseSectionsForCSV(csvfile, [criterion])

            self.assertEqual(sections[0].criterion, criterion)
            self.assertEqual(len(sections[0].rows), 3)

            self.assertEqual(
                sections[0].rows[0],
                "ROBO,EXCHANGE TRADED CONCEPTS TR ROBO GLOBAL ROBOTICS  AND AUTOMATION,10,32.55,305.5,325.50,300.00"
                .split(","))

            self.assertEqual(
                sections[0].rows[1],
                "AAPL,APPLE INC EAI: $2.97 EY: 1.85%,100,157.74,15000.00,15774.00,14000.00"
                .split(","))

            self.assertEqual(
                sections[0].rows[2],
                "V,VISA INC COM CL A EAI: $46.30 EY: 0.76%,20,131.94,2600.00,2638.80,2600.00"
                .split(","))

    def test_bondsSection(self) -> None:
        with open(self.path, newline='') as csvfile:
            criterion = CSVSectionCriterion(startSectionRowMatch=["Bonds"],
                                            endSectionRowMatch=[""],
                                            rowFilter=lambda r: r[0:7])
            sections = parseSectionsForCSV(csvfile, [criterion])

            self.assertEqual(sections[0].criterion, criterion)
            self.assertEqual(len(sections[0].rows), 1)
            self.assertEqual(
                sections[0].rows[0],
                "942792RU5,UNITED STATES TREAS BILLS ZERO CPN ZERO COUPON,10000,98.901,N/A,9890.10,9800.00"
                .split(","))

    def test_optionsSection(self) -> None:
        with open(self.path, newline='') as csvfile:
            criterion = CSVSectionCriterion(startSectionRowMatch=["Options"],
                                            endSectionRowMatch=["", ""],
                                            rowFilter=lambda r: r[1:7])

            sections = parseSectionsForCSV(csvfile, [criterion])

            self.assertEqual(sections[0].criterion, criterion)
            self.assertEqual(len(sections[0].rows), 2)

            self.assertEqual(
                sections[0].rows[0],
                "CALL (SPY) SPDR S&amp;P 500 ETF JAN 25 19 $265 (100 SHS),1,0.25,1394.01,90.01,3456.78"
                .split(","))

            self.assertEqual(
                sections[0].rows[1],
                "PUT (SPY) SPDR S&amp;P 500 ETF MAR 22 19 $189 (100 SHS),10,0.54,876.54,1543.02,5432.78"
                .split(","))


class TestFidelityTransactionsSections(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path('tests/fidelity_transactions.csv')

    def test_transactionsSection(self) -> None:
        with open(self.path, newline='') as csvfile:
            criterion = CSVSectionCriterion(
                startSectionRowMatch=["Run Date", "Account", "Action"],
                endSectionRowMatch=[])
            sections = parseSectionsForCSV(csvfile, [criterion])

            self.assertEqual(sections[0].criterion, criterion)
            self.assertEqual(len(sections[0].rows), 19)

            self.assertEqual(
                sections[0].rows[3],
                helpers.splitAndStripCSVString(
                    "11/9/2017,My Account X12345678, REINVESTMENT, ROBO, EXCHANGE TRADED CONCEPTS TR ROBO GLOBAL, Margin,0,,0.234,USD,32.10,0,,,,-6.78,"
                ))

            self.assertEqual(
                sections[0].rows[4],
                helpers.splitAndStripCSVString(
                    "11/9/2017,My Account X12345678, YOU SOLD             CLOSING TRANSACTION,-SPY180125C260,CALL (SPY) SPDR S&P 500 ETF JAN 25 18 $260 (100 SHS), Margin,0,,-4,USD,0.43,0,4.95,0.08,,89.01,11/02/2017"
                ))

            self.assertEqual(
                sections[0].rows[5],
                helpers.splitAndStripCSVString(
                    "10/26/2017,My Account X12345678,YOU SOLD             EX-DIV DATE 01/02/19RECORD DATE 01/03/19, FXB, INVESCO CURNCYSHS BRIT PND STR BRIT POU, Margin,0,,-16,USD,122.64,0,4.95,0.03,,2345.67,10/28/2017"
                ))

            self.assertEqual(
                sections[0].rows[9],
                helpers.splitAndStripCSVString(
                    "10/10/2017,My Account X12345678, YOU BOUGHT,991696QU2,UNITED STATES TREAS BILLS ZERO CPN 0.00000% 05/9/2018, Margin,0,,10000,USD,98.75,0,,,,-10576.20,"
                ))

            self.assertEqual(
                sections[0].rows[13],
                helpers.splitAndStripCSVString(
                    "9/23/2017,My Account X12345678, YOU BOUGHT, USFD, US FOODS HLDG CORP COM, Margin,0,,178,USD,32.65,0,4.95,,,-5432.10,9/27/2017"
                ))

            self.assertEqual(
                sections[0].rows[14],
                helpers.splitAndStripCSVString(
                    "9/20/2017,My Account X12345678, YOU SOLD, NVDA, NVIDIA CORP, Margin,0,,-12,USD,149.24,0,4.95,0.02,,1487.38,9/23/2017"
                ))

            self.assertEqual(
                sections[0].rows[18],
                helpers.splitAndStripCSVString(
                    "8/2/2017,My Account X12345678, REINVESTMENT, IHI, ISHARES TR U.S. MED DVC ETF, Margin,0,,0.0123,USD,228.25,0,,,,-1.54, "
                ))


class TestVanguardSections(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path('tests/vanguard_positions_and_transactions.csv')

    def test_investmentsSection(self) -> None:
        with open(self.path, newline='') as csvfile:
            criterion = CSVSectionCriterion(
                startSectionRowMatch=["Account Number", "Investment Name"],
                endSectionRowMatch=[],
                rowFilter=lambda r: r[1:6])
            sections = parseSectionsForCSV(csvfile, [criterion])

            self.assertEqual(sections[0].criterion, criterion)
            self.assertEqual(len(sections[0].rows), 6)

            self.assertEqual(
                sections[0].rows[0],
                "VANGUARD TOTAL WORLD STOCK ETF,VT,10,74.81,7481.00".split(
                    ","))

            self.assertEqual(
                sections[0].rows[1],
                "VANGUARD FTSE EMERGING MARKETS ETF,VWO,20,132.68,2653.60".
                split(","))

            self.assertEqual(
                sections[0].rows[2],
                "VANGUARD SP 500 ETF,VOO,100.1,109.60,10970.96".split(","))

            self.assertEqual(
                sections[0].rows[3],
                "VANGUARD TOTAL STOCK MARKET ETF,VTI,50.5,147.78,7462.89".
                split(","))

            self.assertEqual(
                sections[0].rows[4],
                "U S TREASURY BILL CPN  0.00000 % MTD 2017-04-10 DTD 2017-08-14,,5000,99.42100000,4987.65"
                .split(","))

            self.assertEqual(
                sections[0].rows[5],
                "Vanguard Federal Money Market Fund,VMFXX,543.21000,1.0,543.21000"
                .split(","))

    def test_tradesSection(self) -> None:
        with open(self.path, newline='') as csvfile:
            criterion = CSVSectionCriterion(
                startSectionRowMatch=["Account Number", "Trade Date"],
                endSectionRowMatch=[],
                rowFilter=lambda r: r[1:-1])
            sections = parseSectionsForCSV(csvfile, [criterion])

            self.assertEqual(
                sections[0].rows[3],
                "08/20/2017,08/22/2017,Buy,Buy,VANGUARD TOTAL WORLD STOCK ETF,VT,10.0,70.33,-703.30,0.0,-703.30,0.0,Cash"
                .split(","))

            self.assertEqual(
                sections[0].rows[6],
                "02/04/2017,02/06/2017,Reinvestment,Dividend Reinvestment,VANGUARD FTSE EMERGING MARKETS ETF,VWO,0.123,123.4567,-20.15,0.0,-20.15,0.0,Cash"
                .split(","))

            self.assertEqual(
                sections[0].rows[8],
                "02/04/2017,02/06/2017,Reinvestment,Dividend Reinvestment,VANGUARD SP 500 ETF,VOO,0.321,109.3526,-17.48,0.0,-17.48,0.0,Cash"
                .split(","))

            self.assertEqual(
                sections[0].rows[10],
                "01/11/2017,01/13/2017,Buy,Buy,U S TREASURY BILL CPN  0.00000 % MTD 2017-03-10 DTD 2017-09-10,,10000.0,99.345678,-9934.56,0.0,-9934.56,0.0,Cash"
                .split(","))

            self.assertEqual(
                sections[0].rows[11],
                "10/13/2016,10/15/2016,Sell,Sell,VANGUARD FTSE EMERGING MARKETS ETF,VWO,-4.0,110.03,1234.56,0.0,1234.56,0.0,Cash"
                .split(","))

            self.assertEqual(
                sections[0].rows[13],
                "06/26/2016,06/28/2016,Reinvestment,Dividend Reinvestment,VANGUARD TOTAL STOCK MARKET ETF,VTI,0.432,123.5678,-54.32,0.0,-54.32,0.0,Cash"
                .split(","))

            self.assertEqual(
                sections[0].rows[15],
                "04/20/2016,01/22/2017,Buy,Buy,VANGUARD TOTAL STOCK MARKET ETF,VTI,12.0,144.16,-3456.78,0.0,-3456.78,0.0,Cash"
                .split(","))


if __name__ == '__main__':
    unittest.main()
